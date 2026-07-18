# filenotes

filenotes is a small command-line tool for keeping lab-style notes right next to the files they describe. Each note is appended as an entry to a plain Markdown file that lives beside its subject, so your notes stay greppable, portable, and travel with the data. 

## Example

```console
$ note exp_08.npy -m "Baseline run, influctor at setting 1123"
Appended note to exp_08.npy.notes.md

$ note exp_09.npy -m "Bumped to 1253 — cleaner signal, less drift"
Appended note to exp_09.npy.notes.md

$ ls-notes -s                      # one line per file, newest note shown
exp_08.npy: 2026-07-16 15:07:02 Baseline run, influctor at setting 1123
exp_09.npy: 2026-07-16 15:12:15 Bumped to 1253 — cleaner signal, less drift

$ ls exp_08.npy*                   # the note rides along with the data
exp_08.npy   exp_08.npy.notes.md

$ grep -ri "drift" .               # notes are just Markdown — plain grep finds them
./exp_09.npy.notes.md:Bumped to 1253 — cleaner signal, less drift
```

Each note is plain Markdown appended next to its file, so it stays greppable,
travels with the data when you copy or archive the folder, and never lives in a
database you have to keep around.

## Adding notes

You add notes with `note e01.dat -m "Baseline data"` (alias `notes add`), or just `note e01.dat` brigs up $EDITOR (just like `git commit`). You can easliy attach images (`-i`), a screenshot, a region, or clipboard image (`-S`/`-R`/`-C`).

If you just run `note` or `note -m "Some note"` it brings up recent-file picker, so you can quickly drop a note on recent files.

## Viewing notes

Just use `ls-notes` (`notes ls`) for a colored terminal listing, or `cat-notes` (`notes cat`) to concatenate everything in current folder to prepare a quick structured report dump of every note taken, including images.

