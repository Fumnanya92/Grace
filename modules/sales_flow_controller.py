sales_flow_controller.py
class SalesFlowController:
    SALES_STEPS = [
        "greeting",
        "product_inquiry",
        "price_quote",
        "payment_instruction",
        "order_confirmation"
    ]

    def __init__(self):
        self.user_stage = {}

    def get_next_step(self, user_id):
        index = self.user_stage.get(user_id, 0)
        if index < len(self.SALES_STEPS):
            step = self.SALES_STEPS[index]
            self.user_stage[user_id] = index + 1
            return step
        return "complete"

    def reset(self, user_id):
        self.user_stage[user_id] = 0
