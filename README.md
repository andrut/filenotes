# filenotes

filenotes is a small command-line tool for keeping lab-style notes right next to the files they describe. Each note is appended as an entry to a plain Markdown file that lives beside its subject, so your notes stay greppable, portable, and travel with the data. 

## Adding notes

You add notes with `note e01.dat -m "Baseline data"` (alias `notes add`), or just `note e01.dat` brigs up $EDITOR (just like `git commit`). You can easliy attach images (`-i`), a screenshot, a region, or clipboard image (`-S`/`-R`/`-C`).

If you just run `note` or `note -m "Some note"` it brings up recent-file picker, so you can quickly drop a note on recent files.

## Viewing notes

Just use `ls-notes` (`notes ls`) for a colored terminal listing, or `cat-notes` (`notes cat`) to concatenate everything in current folder to prepare a quick structured report dump of every note taken, including images.

