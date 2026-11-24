world Typed {
  entity Sink {
    state seen: int = 0;
    event Apply(n: int);
    event Follow(n: int);
    rule ApplyValue on event Apply {
      transition seen = seen + payload.n;
      emit Follow(n = payload.n) after 1;
    }
    rule FollowValue on event Follow {
      transition seen = seen + payload.n;
    }
  }
}
