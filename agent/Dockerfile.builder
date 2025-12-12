FROM mkaczanowski/packer-builder-arm:latest

# Install extra tools if needed (unzipping the source image)
RUN apt-get update && apt-get install -y unzip wget xz-utils

WORKDIR /build
