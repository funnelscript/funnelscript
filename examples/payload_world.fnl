world Ledger {
  entity Wallet {
    state balance: int = 0;
    state quota: int = 10;
    event Credit(amount: int);

    rule Receive on event Credit {
      transition balance = balance + payload.amount;
    }
    rule Seed on event Start {
      emit Credit(amount = quota) after 2;
      transition quota = 0;
    }
  }
}
