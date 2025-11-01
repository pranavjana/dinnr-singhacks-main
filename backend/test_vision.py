"""Test script to verify Google Cloud Vision API setup."""
import os
import sys

# Set credentials from .env
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "/Users/I758002/dinnr-singhacks/newproject-476920-7f921ad85696.json"

try:
    from google.cloud import vision
    from PIL import Image
    import io
    import requests
    
    print("✓ Google Cloud Vision library imported successfully")
    
    # Test credentials
    client = vision.ImageAnnotatorClient()
    print("✓ Vision API client created successfully")
    
    # Download a test image from the web
    print("\nTesting with a sample image from the web...")
    response = requests.get("https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/400px-Cat03.jpg")
    image_content = response.content
    
    # Create Vision API request
    vision_image = vision.Image(content=image_content)
    web_detection = client.web_detection(image=vision_image)
    
    print("✓ Vision API call successful!")
    print(f"\nWeb Detection Results:")
    print(f"  - Full matching images: {len(web_detection.web_detection.full_matching_images)}")
    print(f"  - Partial matching images: {len(web_detection.web_detection.partial_matching_images)}")
    print(f"  - Pages with matching images: {len(web_detection.web_detection.pages_with_matching_images)}")
    
    if web_detection.web_detection.pages_with_matching_images:
        print(f"\nSample matches:")
        for i, page in enumerate(web_detection.web_detection.pages_with_matching_images[:3]):
            print(f"  {i+1}. {page.url}")
    
    print("\n✅ Google Cloud Vision API is working correctly!")
    
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Run: pip install google-cloud-vision")
    sys.exit(1)
    
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
    print("\nPossible issues:")
    print("1. Check that GOOGLE_APPLICATION_CREDENTIALS points to valid JSON file")
    print("2. Verify the Vision API is enabled in your Google Cloud project")
    print("3. Ensure the service account has Cloud Vision API User role")
    sys.exit(1)
