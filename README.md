# filenotes

filenotes is a small command-line tool for keeping lab-style notes right next to the files they describe. Each note is appended as a timestamped entry to a plain Markdown file that lives beside its subject — `exp_08.npy.notes.md` for a file, `NOTES.md` for a folder — so your notes stay greppable, portable, and travel with the data. You add notes with `note` (aliased under a unified `notes add` interface), which supports quick one-liners (`-m`), a `$EDITOR` session, broadcasting one note across several files, attaching images (`-i`), grabbing a screenshot, region, or clipboard image (`-S`/`-R`/`-C`), a recent-file picker when you run it bare, and automatic git provenance stamps (`commit @ sha (dirty)`) when you work inside a repository. You read them back with `ls-notes` (`notes ls`) for a colored terminal listing, or `cat-notes` (`notes cat`) to concatenate everything — optionally recursing through subfolders — into a single Markdown document suitable for export.

## Archive

The original design sketch that seeded the project lives in [archive/DEVDOC.md](archive/DEVDOC.md).
