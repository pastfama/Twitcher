from PIL import Image

input_file = "watcher_icon.png"
output_file = "watcher.ico"

image = Image.open(input_file)

# Ensure RGBA so transparency is preserved if the PNG has it
image = image.convert("RGBA")

image.save(
    output_file,
    format="ICO",
    sizes=[
        (256, 256),
        (128, 128),
        (64, 64),
        (48, 48),
        (32, 32),
        (16, 16),
    ],
)

print(f"Created: {output_file}")