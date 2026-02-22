from nextocr import NextOCRClient

client = NextOCRClient(
    username="your_username",
    secretkey="your_secretkey"
)

text = client.ocr_image("test.jpg")
print(text)
