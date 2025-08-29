from loguru import logger
import requests
from accounts_trading import AccountsTrading


def design_order(symbol="AAPL", quantity=1, instruction="BUY", order_type="MARKET"):
    return {
        "orderType": order_type,
        "session": "NORMAL",
        "duration": "DAY",
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {
                "instruction": instruction,
                "quantity": quantity,
                "instrument": {"symbol": symbol, "assetType": "EQUITY"},
            }
        ],
    }


def place_order(access_token, account_hash, order_payload):
    url = f"https://api.schwabapi.com/trader/v1/accounts/{account_hash}/orders"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json=order_payload)

    if resp.status_code == 201:
        logger.info("Order placed successfully.")
    else:
        logger.error(f"Order failed: {resp.text}")
    return resp.json()


if __name__ == "__main__":
    # Example usage (replace with your tokens + account hash)
    access_token = "your-access-token"
    account_hash = "your-account-hash"

    order = design_order(symbol="MSFT", quantity=2, instruction="BUY")
    response = place_order(access_token, account_hash, order)
    print(response)
