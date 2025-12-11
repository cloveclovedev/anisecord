import base64
import httpx
import litellm


async def download_and_encode_image(url: str) -> str:
    """Download image from URL and return base64 encoded string."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                image_data = response.content
                return base64.b64encode(image_data).decode('utf-8')
            else:
                raise Exception(f"Failed to download image: HTTP {response.status_code}")
    except Exception as e:
        print(f"Error downloading image: {e}")
        raise


async def call_gemini_api(content, api_key: str) -> str:
    """Call Gemini API with provided content and return response text."""
    response = await litellm.acompletion(
        model="gemini/gemini-2.5-flash",
        messages=[{"role": "user", "content": content}],
        api_key=api_key
    )
    return response.choices[0].message.content

