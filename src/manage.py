#!/usr/bin/env python

import argparse
import sys
from prettytable import PrettyTable
from libdb import LibDb


def handle_insert(parser, args):
    libdb = LibDb()
    for filename in args.library:
        library = libdb.insert(filename)
        if library is not None:
            print "{0}: {1} symbols inserted".format(library.name, len(library.symbols))


def handle_find(parser, args):
    symbols = []
    for symbol in args.symbol + args.symbols:
        try:
            name, addr = symbol.split("=")
            if addr.startswith("0x"):
                addr = int(addr, 16)
            else:
                addr = int(addr)
        except ValueError:
            parser.print_help()
            sys.exit(1)
        symbols.append((name, addr))
    libdb = LibDb()
    table = PrettyTable(["id", "name", "base", "checksum"])
    for library in libdb.find(symbols):
        name, addr = symbols[0]
        base = "0x{0:x}".format(library.calculate_base(name, addr))
        table.add_row([library.id, library.name, base, library.checksum])
    if table.rowcount:
        print table


def handle_symbols(parser, args):
    libdb = LibDb()
    if len(args.identifier) == 64:
        identifier = args.identifier
    else:
        try:
            identifier = int(args.identifier)
        except ValueError:
            parser.print_help()
            sys.exit(1)
    table = PrettyTable(["addr", "name"])
    table.align["name"] = "l"
    library = libdb.library_by_identifier(identifier)
    for symbol in library.iter_symbols():
        table.add_row(["0x{0:08x}".format(symbol.addr), symbol.name])
    if table.rowcount:
        print table


def handle_libraries(parser, args):
    libdb = LibDb()
    table = PrettyTable(["id", "name", "elfclass", "checksum"])
    table.align["name"] = "l"
    for library in libdb.iter_libraries():
        table.add_row([library.id, library.name, library.elfclass, library.checksum])
    if table.rowcount:
        print table


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    find_parser = subparsers.add_parser("find")
    find_parser.set_defaults(func=handle_find)
    find_parser.add_argument("symbol", nargs=1, metavar="symbol",
                             help="e.g.: read=23 write=0x17")
    find_parser.add_argument("symbols", nargs="+", metavar="symbol")

    insert_parser = subparsers.add_parser("insert")
    insert_parser.set_defaults(func=handle_insert)
    insert_parser.add_argument("library", nargs="+")

    symbols_parser = subparsers.add_parser("symbols")
    symbols_parser.set_defaults(func=handle_symbols)
    symbols_parser.add_argument("identifier")

    symbols_parser = subparsers.add_parser("libraries")
    symbols_parser.set_defaults(func=handle_libraries)

    args = parser.parse_args()
    args.func(parser, args)
