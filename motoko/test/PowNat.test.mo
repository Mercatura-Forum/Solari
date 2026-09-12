// Dec.powNat is the correctly rounded power: compared with the exact power, rounded once,
// over random cases at the precisions the computations use. A control proves the comparison
// can fail: a careless power (one guard digit, no rounding test) must be caught.
// Attribution: Thebes Core Team. Licence: Apache 2.0.
import Dec "../src/Dec";
import Nat "mo:core/Nat";
import Debug "mo:core/Debug";
import Runtime "mo:core/Runtime";

var seed : Nat = 20260910;
func next(bound : Nat) : Nat {
  seed := (seed * 6364136223846793005 + 1442695040888963407) % 18446744073709551616;
  (seed / 65536) % bound
};

func exact(x : Dec.Dec, n : Nat, prec : Nat) : Dec.Dec {
  Dec.fix({ neg = x.neg and n % 2 == 1; coef = Nat.pow(x.coef, n); exp = x.exp * n }, prec, #halfEven)
};

func careless(x : Dec.Dec, n : Nat, prec : Nat) : Dec.Dec {
  let w = prec + 1;
  var result : Dec.Dec = Dec.one;
  var base : Dec.Dec = { neg = false; coef = x.coef; exp = x.exp };
  var k = n;
  while (k > 0) {
    if (k % 2 == 1) result := Dec.mul(result, base, w);
    k /= 2;
    if (k > 0) base := Dec.mul(base, base, w);
  };
  Dec.fix({ neg = x.neg and n % 2 == 1; coef = result.coef; exp = result.exp }, prec, #halfEven)
};

func same(a : Dec.Dec, b : Dec.Dec) : Bool { a.neg == b.neg and a.coef == b.coef and a.exp == b.exp };

let precs : [Nat] = [9, 20, 34, 40];
var compared = 0;
var fails = 0;
var caught = 0;
while (compared < 4000) {
  let nd = 1 + next(45);
  var coef = 1 + next(9);
  var i = 1;
  while (i < nd) { coef := coef * 10 + next(10); i += 1 };
  let x : Dec.Dec = { neg = next(5) == 0; coef; exp = -(next(nd + 3) : Int) };
  let n = 1 + next(Nat.min(Nat.max(1, 2500 / nd), 400));
  let prec = precs[next(4)];
  let want = exact(x, n, prec);
  let got = Dec.powNat(x, n, prec);
  if (not same(want, got)) {
    fails += 1;
    if (fails <= 5) Debug.print("FAIL pow coef=" # Nat.toText(coef) # " n=" # Nat.toText(n) # " prec=" # Nat.toText(prec) # " want=" # Dec.toText(want) # " got=" # Dec.toText(got));
  };
  if (not same(want, careless(x, n, prec))) caught += 1;
  compared += 1;
};
// The demonstration's case: a 40-digit rate near 0.08 raised to the 45th power, at 40 digits.
let q : Dec.Dec = { neg = false; coef = 9163000000000000000000000000000000000001; exp = -40 };
if (not same(exact(q, 45, 40), Dec.powNat(q, 45, 40))) { fails += 1; Debug.print("FAIL the demonstration's case") };
compared += 1;

Debug.print("count: powers compared with the exact power = " # Nat.toText(compared));
Debug.print("count: control (careless power) mismatches caught = " # Nat.toText(caught));
if (fails > 0) Runtime.trap(Nat.toText(fails) # " powers differ from the exact power");
if (caught == 0) Runtime.trap("the control was never caught: this comparison proves nothing");
Debug.print("POWNAT GREEN");
