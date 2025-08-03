# GIF to AVIF Converter

A Python tool for converting `.gif` files (or folders containing `.gif`s) and into animated `.avif` files using [`avifenc`](https://github.com/AOMediaCodec/libavif) and [Pillow](https://pypi.org/project/pillow/).

Keeps gif transparency and frame durations intact for the final .avif file

the resulting .avif file is placed in the same folder as the .gif file

---

## Usage
```bash
python gif_to_avif.py path/to/gif_file.gif [--quality N]
```
or

```bash
python gif_to_avif.py path/to/folder/ [--quality N]
```

--quality N: (optional, default 60) (integer: 0 <= N <= 100)
> **Note:** quality above 90 isn't worth the trouble, you won't really see quality improvement and the file size can be bigger than the original .gif file 

Recommended settings:
- basically lossless: 90
- little compression & super high quality: 80
- compression & great quality: 60
- good compression & fine quality: 40
- great compression & some detail: 30
- full compression: 20
- maybe some pixels left: 10

> **Note:** noisy gifs lose their detail faster than smoother gifs, they are also harder to compress

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
