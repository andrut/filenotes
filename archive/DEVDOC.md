Yet another lab notes program. It will be a CLI tool written in python for appending notes. Notes context will be a file, current folder or sometimes current git head. Ok so lets start with basic operation, that is note in context of file. It will be for appending notes for example on experimental result. So say:
```
$ note exp_08.npy -m "Results for using influctor device on setting 1123"
```
And that would append to file "exp_08.npy-NOTES.md" the following text:
```
2026-07-16 15:07:02

Results for using influctor device on setting 1123
```

If I used it like this:
```
$ note exp_08.npy
```
It would open a text area with interactive editor for entring the text but operation would be the same, that is append content to file with notes. Buttons: Save and Cancel. Should we use curses here?

If I used it like this:
```
$ note
```

So without file argument or with argument ".", it would mean that new note will be for current folder and will be appended to file NOTES.md.

There would also be companion tool for listing files with notes and their contents. One would use it like this:
```
$ ls-notes
```
It would list all files that have notes attached to them, sorted by defeault from oldest to newest. Each file listing will show filename on the left and note on the right. So we would see something like that:
```
$ ls-notes
exp_08.npy: 
  2026-07-16 15:07:02

  Results for using influctor device on setting 1123    
exp_09.npy:
  2026-07-16 15:12:15

  Results for using influctor device on setting 1253
```
Ofcourse you can ls-notes for single files if they appear in args. Also there would be a short mode that would collapse each note file contents to single line:
```
$ ls-notes
exp_08.npy: 2026-07-16 15:07:02 Results for using influctor device on setting 1123    
exp_09.npy: 2026-07-16 15:12:15 Results for using influctor device on setting 1253
```

You can use color on output if it goes straight to terminal.

So that's the basic operation for now. Do you have any suggestions before starting work?