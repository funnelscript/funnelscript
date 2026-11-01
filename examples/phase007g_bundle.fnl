world Reusable {
  entity Counter {
    state count: int = 1;
    rule Increment on event Tick { transition count = (count + 2) * 3; }
  }
  agent Visitor {
    state visits: int = 0;
    event Tick(increment: int);
    rule Visit on event Tick { transition visits = visits + payload.increment * 2; }
  }
}
