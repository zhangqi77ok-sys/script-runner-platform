from urllib.request import urlopen

with urlopen("https://example.com", timeout=10) as response:
    print(f"status={response.status}")
