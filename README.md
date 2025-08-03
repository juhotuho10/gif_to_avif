# GIF to AVIF Converter

A Python tool for converting `.gif` files into animated `.avif` files using [`avifenc`](https://github.com/AOMediaCodec/libavif) and [Pillow](https://python-pillow.org/).

Keeps gif transparency and frame durations intact for the final .avif file

---

## Usage
```bash
python gif_to_avif.py path/to/gif_file.gif [--quality N]
```

--quality N: (optional, default 40) (integer: 0 <= N <= 100)

the resulting .avif file is placed in the same folder as the .gif file

---

## Requirements

- Python 3.7+
- [Pillow](https://pypi.org/project/Pillow/)
- [avifenc](https://github.com/AOMediaCodec/libavif) 

> **Note:** `avifenc` must be callable from commandline from the .py file with:
> ```bash 
> avifenc [commands] 
> ```


Install Pillow for python with pip:

```bash
pip install Pillow
```

Install `avifenc`:

Follow [avifenc](https://github.com/AOMediaCodec/libavif?tab=readme-ov-file#installation) installation guide for command line install

or 

download from their [release page](https://github.com/AOMediaCodec/libavif/releases)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
