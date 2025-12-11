from .domain import SnsXConfig

class SnsXConfigRepository:
    def get_config(self, user_id: str) -> SnsXConfig:
        """
        Retrieve SNS-X configuration for a user.
        Currently returns a mock configuration.
        """
        # TODO: Retrieve from persistence layer
        return SnsXConfig(
            user_id=user_id,
            persona="個人事業主の公式アカウントとして振る舞ってください。プロフェッショナルでありながら、親しみやすさを持ち、読者に有益な情報や活動の様子を伝えてください。あまり大げさな表現は避け、誠実なトーンを維持してください。"
        )
