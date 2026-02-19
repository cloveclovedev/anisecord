import traceback
from discord import Interaction, app_commands, Attachment
from discord.ext import commands

from bot.core.user.decorators import feature_enabled
from bot.services.llm.repository import LLMRepository
from bot.services.llm.utils import download_and_encode_image


def create_nutrition_coaching_prompt(
    description: str = None, image_count: int = 0
) -> str:
    """Create structured prompt for nutrition coaching."""
    base_prompt = """As a nutrition coach, analyze the meal(s) and provide nutritional guidance. Focus specifically on:

1. **Calories (kcal)**: Provide a specific estimate and a reasonable range
2. **Protein (g)**: Provide a specific estimate and a reasonable range
3. **Coaching advice**: Practical suggestions for improving nutritional balance
4. **Analysis basis**: Brief explanation of what foods you identified

Format your response EXACTLY as follows:

🍽️ **栄養コーチング結果**

📊 **栄養情報**
• カロリー: [NUMBER] kcal (推定範囲: [LOW]-[HIGH] kcal)
• タンパク質: [NUMBER]g (推定範囲: [LOW]-[HIGH]g)

💡 **コーチングアドバイス**
[Practical coaching suggestions for nutritional improvement]

📝 **分析内容**
[Brief description of identified foods and analysis basis]

📸 **分析画像数: [NUMBER]枚**"""

    if description:
        base_prompt = f"User description: {description}\n\n" + base_prompt

    if image_count == 0:
        base_prompt = base_prompt.replace(
            "📸 **分析画像数: [NUMBER]枚**", "📸 **テキスト説明のみでコーチング**"
        )
    else:
        base_prompt = base_prompt.replace("[NUMBER]", str(image_count))

    return base_prompt


class NutritionCoachCog(commands.Cog):
    """Nutrition coaching functionality using Gemini AI."""

    def __init__(self, bot):
        self.bot = bot
        self.llm_repository = LLMRepository(
            model_name="gemini/gemini-2.5-flash", api_key=self.bot.gemini_api_key
        )

    @app_commands.command(
        name="meal",
        description="Get nutrition coaching for your meal photos and/or description.",
    )
    @feature_enabled("nutrition")
    @app_commands.describe(
        description="Text description of the meal (optional if images are provided)",
        image1="First meal photo (optional)",
        image2="Second meal photo (optional)",
        image3="Third meal photo (optional)",
        image4="Fourth meal photo (optional)",
        image5="Fifth meal photo (optional)",
    )
    async def meal(
        self,
        interaction: Interaction,
        description: str = None,
        image1: Attachment = None,
        image2: Attachment = None,
        image3: Attachment = None,
        image4: Attachment = None,
        image5: Attachment = None,
    ):
        """Get nutrition coaching for your meal."""
        # Defer response to prevent timeout
        await interaction.response.defer()

        # Collect all provided images
        images = [
            img for img in [image1, image2, image3, image4, image5] if img is not None
        ]

        # Validate that at least one input is provided
        if not description and not images:
            await interaction.followup.send(
                "❌ Please provide either a meal description or at least one image."
            )
            return

        # Validate image formats
        supported_formats = [".jpg", ".jpeg", ".png", ".webp"]
        for image in images:
            if not any(
                image.filename.lower().endswith(fmt) for fmt in supported_formats
            ):
                await interaction.followup.send(
                    f"❌ Unsupported image format: {image.filename}. Please use JPG, PNG, or WebP."
                )
                return

        try:
            # Prepare message content
            content = []

            # Add text description if provided
            prompt_text = create_nutrition_coaching_prompt(description, len(images))
            content.append({"type": "text", "text": prompt_text})

            # Process and add images
            print(f"Processing {len(images)} images for meal coaching")
            for i, image in enumerate(images):
                print(f"Downloading and encoding image {i + 1}: {image.filename}")
                base64_image = await download_and_encode_image(image.url)

                # Determine content type from filename
                if image.filename.lower().endswith((".jpg", ".jpeg")):
                    content_type = "image/jpeg"
                elif image.filename.lower().endswith(".png"):
                    content_type = "image/png"
                elif image.filename.lower().endswith(".webp"):
                    content_type = "image/webp"
                else:
                    content_type = "image/jpeg"  # fallback

                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{base64_image}"
                        },
                    }
                )

            # Call Gemini API
            print("Calling Gemini API for meal coaching via Repository")
            response_text = await self.llm_repository.generate_content(content)
            print("Received meal coaching from Gemini")

        except Exception:
            print("An error occurred with the meal coaching API call.")
            traceback.print_exc()
            await interaction.followup.send(
                "❌ An error occurred while providing coaching for your meal. Please try again later."
            )
            return

        await interaction.followup.send(response_text)


async def setup(bot):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(NutritionCoachCog(bot))
