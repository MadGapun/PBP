// #1091: eine 0 bleibt 0, nur Leeres und Unlesbares wird zur Vorgabe.
import assert from "node:assert/strict";
import { zahlOderVorgabe } from "./zahl.js";

assert.equal(zahlOderVorgabe(0, 1), 0);
assert.equal(zahlOderVorgabe("0", 1), 0);
assert.equal(zahlOderVorgabe(7, 1), 7);
assert.equal(zahlOderVorgabe("12", 1), 12);
assert.equal(zahlOderVorgabe("", 1), 1);
assert.equal(zahlOderVorgabe(null, 1), 1);
assert.equal(zahlOderVorgabe(undefined, 1), 1);
assert.equal(zahlOderVorgabe("abc", 1), 1);
console.log("zahl: alle ok");
