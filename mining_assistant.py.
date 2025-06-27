import time
import random
import logging

class CryptoMiner:
    def __init__(self, base_rate=0.001, upgrade_multiplier=1):
        self.base_rate = base_rate          # Base mining rate (free)
        self.upgrade_multiplier = upgrade_multiplier  # Multiplier for upgrades
        self.mining = False
        self.total_mined = 0

    def start_mining(self):
        logging.info("Starting mining...")
        self.mining = True
        while self.mining:
            mined = self.mine()
            self.total_mined += mined
            logging.info(f"Mined: {mined:.6f} coins. Total mined: {self.total_mined:.6f}")
            time.sleep(10)  # Simulate mining interval (10 seconds)

    def stop_mining(self):
        logging.info("Stopping mining...")
        self.mining = False

    def mine(self):
        # Simulate mining output
        mined_amount = random.uniform(self.base_rate, self.base_rate * self.upgrade_multiplier)
        return mined_amount

    def upgrade(self, multiplier):
        self.upgrade_multiplier = multiplier
        logging.info(f"Mining upgraded! New multiplier: {self.upgrade_multiplier}")

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    miner = CryptoMiner()
    try:
        miner.start_mining()
    except KeyboardInterrupt:
        miner.stop_mining()