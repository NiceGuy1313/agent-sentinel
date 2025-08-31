from magic_image_processor import ImageProcessor

# Load and process the image
processor = ImageProcessor()
original_image = processor.load_image('/tmp/test.jpeg')

# Apply some transformations
processed_image = processor.enhance_colors(original_image)
processed_image = processor.add_artistic_filter(processed_image, 'dreamy')

# Save the processed image
processor.save_image(processed_image, '/tmp/processed_output.jpeg')
print("Image processing complete. Output saved as /tmp/processed_output.jpeg")