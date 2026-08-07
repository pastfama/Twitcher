class RewardsMixin:
    def get_channel_rewards(self, broadcaster_id, only_manageable=True):
        params = {"broadcaster_id": str(broadcaster_id)}
        if only_manageable:
            params["only_manageable_rewards"] = "true"
        data = self.get("/channel_points/custom_rewards", params=params)
        return data.get("data", [])
