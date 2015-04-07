#!/usr/bin/env python

import os
from collections import defaultdict
from StringIO import StringIO
from hashlib import sha256 as hash_algo
from itertools import chain, tee, izip
from prettytable import PrettyTable
from elftools.elf.elffile import ELFFile
from sqlalchemy import (
    create_engine, func, distinct, Column, Integer, String, ForeignKey, and_
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (
    sessionmaker, relationship, backref, object_session, scoped_session
)
from sqlalchemy.orm.exc import NoResultFound
import config


DIGEST_SIZE = len(hash_algo("").hexdigest())


engine = create_engine(config.CONNECTION_STRING)
Base = declarative_base()


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return izip(a, b)


class Symbol(Base):
    __tablename__ = "symbols"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    addr = Column(Integer, nullable=False)
    #FIXME: add a whole lot of other symbol information
    library_id = Column(Integer, ForeignKey("libraries.id"), nullable=False)
    library = relationship("Library", backref=backref("symbols", order_by=id))

    def __repr__(self):
        return 'Symbol(name="{0}", addr=0x{1:x})'.format(self.name, self.addr)


class Library(Base):
    __tablename__ = "libraries"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    checksum = Column(String(DIGEST_SIZE), unique=True)
    elfclass = Column(Integer)
    filepath = Column(String)
    machine_arch = Column(String)

    def calculate_base(self, symbol_name, addr):
        session = object_session(self)
        filter_args = {"library_id": self.id, "name": symbol_name}
        try:
           symbol = session.query(Symbol).filter_by(**filter_args).one()
        except NoResultFound:
            return None
        return addr - symbol.addr

    def iter_symbols(self):
        session = object_session(self)
        query = session.query(Symbol).filter(Symbol.library_id==self.id) \
                                          .order_by(Symbol.addr)
        for symbol in query.yield_per(200):
            yield symbol

    def symbols(self):
        return list(self.iter_symbols())


def library_to_sqlalchemy(filepath, filename=None):
    with open(filepath) as fileobj:
        elf_data = fileobj.read()
    checksum = hash_algo(elf_data).hexdigest()
    if filename is None:
        filename = os.path.basename(filepath)
    elf = ELFFile(StringIO(elf_data))
    library = Library(name=filename, checksum=checksum, filepath=filepath,
                      elfclass=elf.elfclass, machine_arch=elf.get_machine_arch())
    symtab = elf.get_section_by_name(".symtab")
    dynsym = elf.get_section_by_name(".dynsym")
    if not symtab and not dynsym:
        raise Exception("No symbol table found")
    elif symtab and dynsym:
        symbols = chain(symtab.iter_symbols(), dynsym.iter_symbols())
    elif symtab:
        symbols = symtab.iter_symbols()
    else:
        symbols = dynsym.iter_symbols()
    seen_symbols = set()
    symbol_entities = []
    for symbol in symbols:
        if not symbol.name or not symbol.entry["st_value"] or \
            symbol.name in seen_symbols:
            continue
        symbol_entities.append(Symbol(name=symbol.name,
                                      addr=symbol.entry["st_value"],
                                      library=library))
        seen_symbols.add(symbol.name)
    return library, symbol_entities


class LibDb(object):
    def __init__(self):
        self.Session = scoped_session(sessionmaker())
        self.Session.configure(bind=engine)
        self.session = self.Session()

    def insert(self, filepath, filename=None, force=False):
        with open(filepath) as fileobj:
            checksum = hash_algo(fileobj.read()).hexdigest()
        if not force and self.session.query(Library).filter(Library.checksum==checksum).first():
            return None
        try:
            library, symbols = library_to_sqlalchemy(filepath, filename)
            self.session.add(library)
            for symbol in symbols:
                self.session.add(symbol)
            self.session.commit()
            return library
        except Exception, e:
            print e
            self.session.rollback()

    def find(self, symbols):
        symbol_dict = {name: addr for name, addr in symbols}
        symbol_names = symbol_dict.keys()
        query = self.session.query(Library, Symbol) \
                                .join(Symbol) \
                                .filter(Symbol.name.in_(symbol_names))
        libraries = defaultdict(list)
        for library, symbol in query:
            libraries[library].append(symbol)
        matching_libraries = []
        for library, symbols in libraries.iteritems():
            if len(symbol_names) != len(symbols): # not all symbols found in library
                continue
            for sym1, sym2 in pairwise(symbols):
                diff = symbol_dict[sym1.name] - symbol_dict[sym2.name]
                if sym1.addr - sym2.addr != diff:
                    break
            else:
                base_addr = symbol_dict[symbols[0].name] - symbols[0].addr
                matching_libraries.append((library, base_addr))
        return sorted(matching_libraries,
            cmp=lambda (a, _), (b, __): cmp(a.id, b.id))

    def iter_libraries(self):
        for library in self.session.query(Library).yield_per(1000):
            yield library

    def libraries(self):
        return list(self.iter_libraries())

    def library_by_identifier(self, identifier):
        if isinstance(identifier, (int, long)):
            expression = Library.id == identifier
        elif len(identifier) == DIGEST_SIZE:
            expression = Library.checksum == identifier
        else:
            raise ValueError("Unknown library_identifier")
        query = self.session.query(Library).filter(expression)
        return query.first()

    def iter_symbols(self, name=None):
        query = self.session.query(Symbol)
        if name is not None:
            query = query.filter(Symbol.name.like(name))
        for symbol in query.yield_per(1000):
            yield symbol

    def symbols(self, name=None):
        return list(self.iter_symbols(name))


Base.metadata.create_all(engine)
