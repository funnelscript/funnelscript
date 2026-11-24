// Demonstrates pure, self-scheduled World reactions on a single agent.
world ChainDemo {
  agent Worker {
    state progress: int = 0;
    state active: bool = false;

    rule Begin on event Start {
      transition active = true;
      emit Step after 2;
    }

    rule Advance on event Step {
      transition progress = progress + 1;
      emit Stop after 3;
    }

    rule Finish on event Stop {
      transition active = false;
    }
  }
}
