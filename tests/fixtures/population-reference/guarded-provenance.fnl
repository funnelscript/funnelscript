world GuardedProvenance {
  agent Visitor {
    state phase: string = "new";
    state permitted: bool = false;
    rule TickRule on event Tick when (permitted == true) {
      transition phase = "terminal";
    }
  }
}
