#!/usr/bin/env python2

import os
from os import path
from flask import (
    Flask, render_template, request, url_for, redirect, send_from_directory,
    jsonify
)
from libdb import LibDb, hash_algo
import config

libdb = LibDb()

app = Flask(__name__)


def parse_int(string):
    if string.startswith("0x"):
        return int(string, 16)
    return int(string)


@app.route("/")
def index():
    return redirect("upload")


@app.route("/download/<identifier>")
def download(identifier):
    library = libdb.library_by_identifier(identifier)
    return send_from_directory(config.LIBRARY_DIR, identifier,
        as_attachment=True, attachment_filename=library.name)


@app.route("/libraries")
def libraries():
    return render_template("libraries.html", libraries=libdb.iter_libraries())


@app.route("/symbols/completion")
def complete_symbol():
    symbols = set(
        symbol.name for symbol in libdb.symbols(request.args.get("name", ""))
    )
    return jsonify({"symbols": list(symbols)})


@app.route("/library/<identifier>")
def library(identifier):
    library = libdb.library_by_identifier(identifier)
    return render_template("library.html", library=library)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files['file']
        bytes = file.read()
        hash = hash_algo(bytes).hexdigest()
        local_path = path.join(config.LIBRARY_DIR, hash)
        try:
            fd = os.open(local_path, os.O_CREAT | os.O_EXCL)
        except OSError:
            pass
        else:
            os.close(fd)
            file.seek(0)
            file.save(local_path)
            print libdb.insert(local_path, file.filename)
        return redirect(url_for("library", identifier=hash))
    else:
        return render_template("upload.html")


@app.route("/search", methods=["GET", "POST"])
def search():
    from time import time
    if request.method == "POST":
        names = request.form.getlist("name[]")
        addrs = map(parse_int, request.form.getlist("addr[]"))
        symbols = zip(names, addrs)
        libraries = libdb.find(symbols)
        return render_template("search.html", libraries=libraries,
            symbols=symbols)
    else:
        return render_template("search.html", symbols=[("", "")] * 2)


@app.teardown_appcontext
def shutdown_session(exception=None):
    libdb.Session.remove()


if __name__ == '__main__':
    app.run(debug=False)
