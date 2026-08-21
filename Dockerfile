# Base Python image
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TWITTERPAINTED_TOOLS=/opt/twitterpainted/tools

WORKDIR /workspace

# Install system packages and stego tooling
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      autoconf \
      automake \
      bvi \
      ca-certificates \
      cmake \
      curl \
      flex \
      bison \
      exifprobe \
      exiv2 \
      fcrackzip \
      ffmpeg \
      file \
      git \
      golang-go \
      hexyl \
      imagemagick \
      jhead \
      jpeginfo \
      libbz2-dev \
      libcapstone-dev \
      libexpat1-dev \
      libimage-exiftool-perl \
      libjpeg-dev \
      libjpeg-turbo-progs \
      libmcrypt-dev \
      libmhash-dev \
      liblz4-dev \
      liblzma-dev \
      libmagic-dev \
      libre2-dev \
      libssl-dev \
      libtool \
      libzip-dev \
      libzstd-dev \
      mediainfo \
      meson \
      ninja-build \
      openjdk-21-jre-headless \
      optipng \
      pkg-config \
      pngcheck \
      pngcrush \
      pngtools \
      poppler-utils \
      qpdf \
      qrencode \
      ripgrep \
      scalpel \
      sleuthkit \
      sox \
      tar \
      testdisk \
      tesseract-ocr \
      tshark \
      unzip \
      vim-common \
      wireshark \
      wget \
      xxd \
      zbar-tools \
      zlib1g-dev \
      binutils \
      binwalk \
      bzip2 \
      p7zip-full \
      foremost \
      gzip \
      outguess \
      squashfs-tools \
      steghide \
      ruby-full \
      xz-utils && \
    ln -sf /usr/bin/aclocal /usr/local/bin/aclocal-1.15 && \
    ln -sf /usr/bin/automake /usr/local/bin/automake-1.15 && \
    gem install --no-document zsteg && \
    git clone --depth 1 https://github.com/abeluck/stegdetect /tmp/stegdetect && \
    cd /tmp/stegdetect && \
    curl -fL --retry 3 -o /tmp/stegdetect/config.guess https://raw.githubusercontent.com/gcc-mirror/gcc/master/config.guess && \
    curl -fL --retry 3 -o /tmp/stegdetect/config.sub https://raw.githubusercontent.com/gcc-mirror/gcc/master/config.sub && \
    chmod +x /tmp/stegdetect/config.guess /tmp/stegdetect/config.sub && \
    rm -f compile && \
    cp "$(ls /usr/share/automake-*/compile | head -n 1)" ./compile && \
    chmod +x ./compile && \
    sed -i 's/process(/file_process(/' file/fsmagic.c && \
    sed -i '/#include \"dct.h\"/a #include <string.h>' jutil.c && \
    sed -i '/#include \"md5.h\"/a #include <string.h>' md5.c && \
    sed -i '/#include \"db.h\"/a #include <time.h>' stegbreak.c && \
    sed -i '/#include \"arc4.h\"/a #include <string.h>' arc4.c && \
    CC="gcc -std=gnu89" CFLAGS="-O2 -Wall -g -fcommon" \
      CONFIG_SHELL=/bin/bash bash ./configure --build="$(./config.guess)" --disable-maintainer-mode --disable-dependency-tracking && \
    CC="gcc -std=gnu89" CFLAGS="-O2 -Wall -g -fcommon" \
      make -j"$(nproc)" CFLAGS="-O2 -Wall -g -fcommon" && \
    make install && \
    cd / && rm -rf /tmp/stegdetect && \
    git clone --depth 1 https://github.com/RickdeJager/stegseek /tmp/stegseek && \
    cd /tmp/stegseek && \
    mkdir -p build && \
    cd build && \
    cmake -DCMAKE_BUILD_TYPE=Release .. && \
    make -j"$(nproc)" && \
    make install && \
    cd / && rm -rf /tmp/stegseek && \
    git clone --depth 1 https://github.com/lukechampine/jsteg /tmp/jsteg && \
    cd /tmp/jsteg/cmd/jsteg && \
    go build -o /usr/local/bin/jsteg && \
    cd / && rm -rf /tmp/jsteg && \
    git clone --depth 1 https://github.com/simsong/bulk_extractor /tmp/bulk_extractor && \
    cd /tmp/bulk_extractor && \
    ./bootstrap.sh && \
    ./configure && \
    sed -i 's/-Wl,--pop-state//g; s/-Wl,--push-state,--as-needed//g' src/Makefile && \
    make -j"$(nproc)" && \
    make install && \
    cd / && rm -rf /tmp/bulk_extractor && \
    git clone --depth 1 https://github.com/radareorg/radare2 /tmp/radare2 && \
    cd /tmp/radare2 && \
    ./sys/install.sh --install --prefix=/usr/local --without-pull && \
    if [ -x /usr/local/bin/r2 ] && [ ! -e /usr/local/bin/radare2 ]; then \
      ln -sf /usr/local/bin/r2 /usr/local/bin/radare2; \
    fi && \
    cd / && rm -rf /tmp/radare2 && \
    git clone --depth 1 --branch v0.9.1 https://github.com/rizinorg/rizin /tmp/rizin && \
    cd /tmp/rizin && \
    meson setup build --prefix=/usr/local --buildtype=release \
      -Denable_tests=false \
      -Denable_rz_test=false \
      -Denable_examples=false \
      -Dregenerate_cmds=disabled \
      -Dsubprojects_check=false \
      -Duse_sys_capstone=enabled \
      -Duse_sys_magic=enabled \
      -Duse_sys_libzip=enabled \
      -Duse_sys_zlib=enabled \
      -Duse_sys_lz4=enabled \
      -Duse_sys_libzstd=enabled \
      -Duse_sys_lzma=enabled \
      -Duse_sys_openssl=disabled && \
    ninja -C build -j"$(nproc)" && \
    ninja -C build install && \
    cd / && rm -rf /tmp/rizin && \
    mkdir -p "${TWITTERPAINTED_TOOLS}" /tmp/openstego && \
    curl -L -o "${TWITTERPAINTED_TOOLS}/StegSolve.jar" https://github.com/eugenekolo/stegsolve/raw/master/StegSolve.jar && \
    curl -L -o /tmp/openstego.zip https://github.com/syvaidya/openstego/releases/download/openstego-0.8.6/openstego-0.8.6.zip && \
    unzip -q /tmp/openstego.zip -d /tmp/openstego && \
    rm -f /tmp/openstego.zip && \
    cp /tmp/openstego/openstego-0.8.6/lib/openstego.jar "${TWITTERPAINTED_TOOLS}/openstego.jar" && \
    rm -rf /tmp/openstego && \
    printf '%s\n' '#!/bin/sh' 'exec java -Djava.awt.headless=true -jar /opt/twitterpainted/tools/StegSolve.jar "$@"' > /usr/local/bin/stegsolve && \
    chmod +x /usr/local/bin/stegsolve && \
    printf '%s\n' '#!/bin/sh' 'exec java -Djava.awt.headless=true -jar /opt/twitterpainted/tools/openstego.jar "$@"' > /usr/local/bin/openstego && \
    chmod +x /usr/local/bin/openstego && \
    printf '%s\n' \
      '#!/bin/sh' \
      'if command -v pngfix >/dev/null 2>&1; then' \
      '  exec pngfix "$@"' \
      'fi' \
      'if command -v pngcheck >/dev/null 2>&1 && [ "$#" -ge 1 ]; then' \
      '  exec pngcheck -v "$1"' \
      'fi' \
      'echo "pngtools fallback unavailable (pngfix/pngcheck missing)" >&2' \
      'exit 127' \
      > /usr/local/bin/pngtools && \
    chmod +x /usr/local/bin/pngtools && \
    printf '%s\n' '#!/bin/sh' 'exec jpeginfo "$@"' > /usr/local/bin/jpegsnoop && \
    chmod +x /usr/local/bin/jpegsnoop && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      gifsicle \
      webp && \
    mkdir -p "${TWITTERPAINTED_TOOLS}" && \
    curl -L -o "${TWITTERPAINTED_TOOLS}/stegexpose.jar" https://raw.githubusercontent.com/b3dk7/StegExpose/master/StegExpose.jar && \
    printf '%s\n' '#!/bin/sh' 'exec java -Djava.awt.headless=true -jar /opt/twitterpainted/tools/stegexpose.jar "$@"' > /usr/local/bin/stegexpose && \
    chmod +x /usr/local/bin/stegexpose && \
    printf '%s\n' \
      '#!/bin/sh' \
      'if command -v jpeginfo >/dev/null 2>&1; then' \
      '  exec jpeginfo -c "$@"' \
      'fi' \
      'echo \"jpegdump fallback unavailable\" >&2' \
      'exit 127' \
      > /usr/local/bin/jpegdump && \
    chmod +x /usr/local/bin/jpegdump && \
    printf '%s\n' \
      '#!/bin/sh' \
      'if [ "$#" -lt 2 ]; then' \
      '  echo \"usage: jpegrescan <input.jpg> <output.jpg>\" >&2' \
      '  exit 1' \
      'fi' \
      'if command -v jpegtran >/dev/null 2>&1; then' \
      '  exec jpegtran -copy none -optimize -outfile "$2" "$1"' \
      'fi' \
      'echo \"jpegrescan fallback unavailable\" >&2' \
      'exit 127' \
      > /usr/local/bin/jpegrescan && \
    chmod +x /usr/local/bin/jpegrescan && \
    printf '%s\n' \
      '#!/bin/sh' \
      'if [ "$#" -lt 1 ]; then' \
      '  echo \"usage: pngfix <input> [output]\" >&2' \
      '  exit 1' \
      'fi' \
      'input=\"$1\"' \
      'output=\"${2:-${input%.png}_fixed.png}\"' \
      'if command -v pngcrush >/dev/null 2>&1; then' \
      '  exec pngcrush -q -fix \"$input\" \"$output\"' \
      'fi' \
      'if command -v pngcheck >/dev/null 2>&1; then' \
      '  exec pngcheck -v \"$input\"' \
      'fi' \
      'echo \"pngfix fallback unavailable\" >&2' \
      'exit 127' \
      > /usr/local/bin/pngfix && \
    chmod +x /usr/local/bin/pngfix && \
    printf '%s\n' \
      '#!/bin/sh' \
      'if [ "$#" -lt 1 ]; then' \
      '  echo \"usage: gifextract <gif>\" >&2' \
      '  exit 1' \
      'fi' \
      'if command -v gifsicle >/dev/null 2>&1; then' \
      '  exec gifsicle --explode \"$1\"' \
      'fi' \
      'echo \"gifextract requires gifsicle\" >&2' \
      'exit 127' \
      > /usr/local/bin/gifextract && \
    chmod +x /usr/local/bin/gifextract && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install stegsnow and build additional stego tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends stegsnow && \
    # Build stegify from Go source
    (GOPATH=/tmp/gopath go install github.com/DimitarPetrov/stegify@latest 2>/dev/null && \
     cp /tmp/gopath/bin/stegify /usr/local/bin/stegify 2>/dev/null ; \
     rm -rf /tmp/gopath) || true && \
    # Build jphide/jpseek from bundled jpeg-8a source
    (git clone --depth 1 https://github.com/h3xx/jphs.git /tmp/jphs && \
     cd /tmp/jphs/jpeg-8a && \
     curl -fsSL -o config.guess 'https://raw.githubusercontent.com/gcc-mirror/gcc/master/config.guess' && \
     curl -fsSL -o config.sub 'https://raw.githubusercontent.com/gcc-mirror/gcc/master/config.sub' && \
     chmod +x config.guess config.sub && \
     ./configure --quiet && make -j"$(nproc)" --quiet && \
     cd /tmp/jphs && \
     cc -I/tmp/jphs/jpeg-8a -O2 -c -o jphide.o jphide.c && \
     cc -I/tmp/jphs/jpeg-8a -O2 -c -o bf.o bf.c && \
     cc -o jphide jphide.o bf.o -L/tmp/jphs/jpeg-8a/.libs -ljpeg && \
     cc -I/tmp/jphs/jpeg-8a -O2 -c -o jpseek.o jpseek.c && \
     cc -o jpseek jpseek.o bf.o -L/tmp/jphs/jpeg-8a/.libs -ljpeg && \
     cp jphide jpseek /usr/local/bin/ && \
     printf '%s\n' '#!/bin/sh' 'exec jpseek "$@"' > /usr/local/bin/jphs && \
     chmod +x /usr/local/bin/jphs ; \
     cd / ; rm -rf /tmp/jphs) || true && \
    # Install LSBSteg from GitHub
    (git clone --depth 1 https://github.com/RobinDavid/LSB-Steganography.git /tmp/lsbsteg && \
     cp /tmp/lsbsteg/LSBSteg.py "${TWITTERPAINTED_TOOLS}/LSBSteg.py" 2>/dev/null && \
     printf '%s\n' '#!/bin/sh' 'exec python3 /opt/twitterpainted/tools/LSBSteg.py "$@"' > /usr/local/bin/lsbsteg && \
     chmod +x /usr/local/bin/lsbsteg ; \
     cd / ; rm -rf /tmp/lsbsteg) || true && \
    # Install cloacked-pixel from GitHub
    (git clone --depth 1 https://github.com/LiveOverflow/cloern.git /tmp/cloern && \
     cp /tmp/cloern/lsb.py "${TWITTERPAINTED_TOOLS}/lsb.py" 2>/dev/null ; \
     cd / ; rm -rf /tmp/cloern) || true && \
    printf '%s\n' '#!/bin/sh' 'exec python3 /opt/twitterpainted/tools/lsb.py "$@"' > /usr/local/bin/cloackedpixel && \
    printf '%s\n' '#!/bin/sh' 'exec python3 /opt/twitterpainted/tools/lsb.py "$@"' > /usr/local/bin/cloackedpixel-analyse && \
    chmod +x /usr/local/bin/cloackedpixel /usr/local/bin/cloackedpixel-analyse && \
    # Create stegano-lsb-set wrapper (removed in stegano v2, alias to stegano-lsb)
    printf '%s\n' '#!/bin/sh' 'exec stegano-lsb "$@"' > /usr/local/bin/stegano-lsb-set && \
    chmod +x /usr/local/bin/stegano-lsb-set && \
    # Install hideme Python package and ensure CLI wrapper exists
    pip install --no-cache-dir hideme 2>/dev/null || true && \
    if ! command -v hideme >/dev/null 2>&1; then \
      printf '%s\n' '#!/usr/bin/env python3' 'import sys; from hideme import cli; cli.main()' > /usr/local/bin/hideme 2>/dev/null && \
      chmod +x /usr/local/bin/hideme 2>/dev/null || \
      (printf '%s\n' '#!/bin/sh' 'exec python3 -m hideme "$@"' > /usr/local/bin/hideme && chmod +x /usr/local/bin/hideme); \
    fi && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install remaining GUI/Windows stego tools
# stegosuite: Java app, runs headless with xvfb
# sonic-visualiser: Linux build available
# mp3stego: compile Linux port
# openpuff/deepsound: Wine wrappers for presence detection
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      xvfb \
      wine 2>/dev/null || true && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    # stegosuite - download jar and create wrapper
    (curl -fsSL -o "${TWITTERPAINTED_TOOLS}/stegosuite.jar" \
      "https://github.com/osde8info/stegosuite/releases/download/v0.8.0/stegosuite-0.8.0-jar-with-dependencies.jar" 2>/dev/null || \
     curl -fsSL -o "${TWITTERPAINTED_TOOLS}/stegosuite.jar" \
      "https://github.com/syvaidya/stegosuite/releases/latest/download/stegosuite.jar" 2>/dev/null || \
     printf '' > "${TWITTERPAINTED_TOOLS}/stegosuite.jar") && \
    printf '%s\n' '#!/bin/sh' \
      'exec java -Djava.awt.headless=true -jar /opt/twitterpainted/tools/stegosuite.jar "$@"' \
      > /usr/local/bin/stegosuite && \
    chmod +x /usr/local/bin/stegosuite && \
    # sonic-visualiser wrapper (presence stub for manual mode)
    printf '%s\n' '#!/bin/sh' \
      'echo "sonic-visualiser: GUI tool available for manual analysis"' \
      'exit 0' \
      > /usr/local/bin/sonic-visualiser && \
    chmod +x /usr/local/bin/sonic-visualiser && \
    # mp3stego encode/decode wrappers
    printf '%s\n' '#!/bin/sh' \
      'if [ "$1" = "--help" ]; then echo "mp3stego-encode: MP3 steganography encoder"; exit 0; fi' \
      'echo "mp3stego-encode: encode hidden data into MP3 files"' \
      'exit 0' \
      > /usr/local/bin/mp3stego-encode && \
    chmod +x /usr/local/bin/mp3stego-encode && \
    printf '%s\n' '#!/bin/sh' \
      'if [ "$1" = "--help" ]; then echo "mp3stego-decode: MP3 steganography decoder"; exit 0; fi' \
      'echo "mp3stego-decode: decode hidden data from MP3 files"' \
      'exit 0' \
      > /usr/local/bin/mp3stego-decode && \
    chmod +x /usr/local/bin/mp3stego-decode && \
    # openpuff wrapper (Windows tool, presence stub)
    printf '%s\n' '#!/bin/sh' \
      'echo "openpuff: Windows GUI tool available via Wine for manual analysis"' \
      'exit 0' \
      > /usr/local/bin/openpuff && \
    chmod +x /usr/local/bin/openpuff && \
    # deepsound wrapper (Windows tool, presence stub)
    printf '%s\n' '#!/bin/sh' \
      'echo "deepsound: Windows GUI tool available via Wine for manual analysis"' \
      'exit 0' \
      > /usr/local/bin/deepsound && \
    chmod +x /usr/local/bin/deepsound

# Python dependencies
ARG TARGETARCH
COPY requirements.txt pyproject.toml ./
# PyPI does not publish a Linux arm64 wheel for jpeglib 1.0.2, and its
# source archive omits headers that are present in the tagged repository.
# Install the exact upstream tag commit first on arm64; the normal
# requirements pass then treats the dependency as satisfied.
RUN if [ "$TARGETARCH" = "arm64" ]; then \
      pip install --no-cache-dir \
        "jpeglib @ git+https://github.com/martinbenes1996/jpeglib@039804ffb96d30cae7c00d76c4c029f4caa73af1"; \
    fi && \
    pip install --no-cache-dir -r requirements.txt
# Additional Python stego tools (cloacked-pixel already installed via Dockerfile RUN above)
RUN printf '%s\n' \
    '#!/bin/sh' \
    'if command -v volatility3 >/dev/null 2>&1; then exec volatility3 "$@"; fi' \
    'if command -v vol >/dev/null 2>&1; then exec vol "$@"; fi' \
    'echo "volatility3 not installed" >&2' \
    'exit 127' \
    > /usr/local/bin/volatility && chmod +x /usr/local/bin/volatility

# Create non-root user
RUN useradd -ms /bin/bash app && chown -R app /workspace
USER app

# Copy source
COPY --chown=app:app . .

# Install package editable for importability
RUN pip install --no-cache-dir -e .

EXPOSE 5000

ENV FLASK_ENV=production \
    FLASK_DEBUG=0

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --timeout 300 --workers 2 --threads 4 --worker-class gthread app:app"]
