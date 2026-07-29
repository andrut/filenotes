# Filenotes
It's a small command-line tool for keeping lab-style notes right next to the files they describe. Each note is appended as an entry to a plain MD file that lives beside its subject, so your notes stay greppable, portable, and travel with the data. 

## Disclaimer 
[![AI-assisted development](https://img.shields.io/badge/development-AI--assisted-6f42c1)](#ai-assisted-development)

This is only a prototype built for my day-to-day personal notetaking; It's mostly coded with agents but I just think it's cool, useful, quite elegant and that's why I share it in the open. 

## Example

That's how you leave a note on file `result-8.data`:
```console
$ note result-8.data -m "Baseline run, setting at 1123"
Appended note to result-8.data.notes.md
```

Say we got another file `result-10.data` and want to leave note there:
```console
$ note result-10.data -m "Bumped to 1253. Observed less drift"
Appended note to result-10.data.notes.md
```

Let's list notes in current dir with `ls-notes`; `-s` is for short `summary` format:
```console
$ ls-notes -s
result-8.data 2026-07-16 15:07:02 Baseline run, setting at 1123
result-10.data 2026-07-16 15:12:15 Bumped to 1253. Observed less drift

$ ls result-8.*                   # the note rides along with the data
result-8.data   result-8.data.notes.md

$ grep -ri "drift" .              # notes are just Markdown — plain grep finds them
./result-10.data.notes.md:Bumped to 1253. Observed less drift
```

Each note is plain Markdown appended next to its file, so it stays greppable,
travels with the data when you copy or archive the folder, and never lives in a
database you have to keep around.

And this is how to add a note with a screenshot; `-S` entire screen, `-R` let user select a region of the screen
```console
$ note points.npz -m "Points look uniform. TODO: check that" -R
```
That command will wait for user to select region of the screen, then put that screenshot into `notes-assets` folder and append that image to MD file with a message. If you use `-E`, then image will be embedded inside MD file.

## The why

I built it for self, because during research work I tend to produce a lot of files with timestamps for filenames and often its hard and tedious to keep track of everything. Using this tool I can quickly drop some notes for future me, attach a screenshot of a plot, put some context on why and how or just drop some other adhoc notes. There are many tools like that but I needed something superfast to use and wanted notes to live next to the data they describe.

# Usage

## Adding notes

You add notes with `note e01.dat -m "Baseline data"` (alias `notes add`), or just `note e01.dat` brigs up $EDITOR (just like `git commit`). You can easliy attach images (`-i`), a screenshot, a region, or clipboard image (`-S`/`-R`/`-C`).

If you just run `note` or `note -m "Some note"` it brings up recent-file picker, so you can quickly drop a note on recent files.

## Viewing notes

Just use `ls-notes` (`notes ls`) for a colored terminal listing. 

Use `cat-notes` (`notes cat`) to concatenate everything in current folder to prepare a quick structured report dump of every note taken, including images in a single MD output.

# Installation

Filenotes is pure Python (3.9+). The easiest way to install is with [pipx](https://pipx.pypa.io), which drops it in its own isolated environment and puts the `note`, `ls-notes`, `cat-notes` and `notes` commands on your PATH.

First, get pipx if you don't have it:

- **Linux:** `sudo apt install pipx`  (or `python3 -m pip install --user pipx`)
- **macOS:** `brew install pipx`

then run `pipx ensurepath` once and open a new terminal.

## From GitHub (one-liner)

Command line only:
```console
$ pipx install git+https://github.com/andrut/filenotes.git
```

With the desktop GUI (`notes-gui`):
```console
$ pipx install "filenotes[gui] @ git+https://github.com/andrut/filenotes.git"
```

## From a local clone

Download (or `git clone`) the repo first, then run from inside it:
```console
$ git clone https://github.com/andrut/filenotes.git
$ cd filenotes
$ pipx install .            # add ".[gui]" instead for the GUI
```

## Notes

- **Screenshots and clipboard** (`-S`/`-R`/`-C`): the CLI shells out to native tools. macOS already ships them (`screencapture`, `pbpaste`); on Linux install whatever matches your session, e.g. `grim`+`slurp` on Wayland, or `maim`/`scrot`+`xclip` on X11.
- **GUI on the newest Python:** PySide6 wheels lag the very newest Python (e.g. 3.14). If a `[gui]` install fails, point pipx at a supported interpreter, e.g. `--python /usr/bin/python3`.
- **Developing:** add `--editable` to a local install so code changes take effect without reinstalling: `pipx install --editable ".[gui]"`.

