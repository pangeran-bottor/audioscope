# data/

Audio files are not bundled with this repository. Drop your own recordings here (or pass
any path on the command line) to run the analyzer.

```bash
# place files, e.g. data/sample_001.wav, then:
audioscope analyze data/sample_001.wav
audioscope analyze data/                # batch: every audio file in this folder
```

Supported extensions: `.wav .mp3 .m4a .flac .aac .ogg .opus .wma`.

Everything in this folder except this README is git-ignored, so audio never gets committed.
See [`../examples/`](../examples/) for sample reports produced by the tool.
