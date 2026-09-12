/// Hash.mo — SHA-256 (FIPS 180-4) over bytes, as lowercase hex: the fingerprint
/// recorded for every imported source file (`hashlib.sha256(bytes).hexdigest()`).
///
/// Attribution: Thebes Core Team. Licence: Apache 2.0.

import Sha256 "mo:sha2/Sha256";
import Char "mo:core/Char";
import Nat8 "mo:core/Nat8";

module {
  let HEX : [Char] = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'];

  public func hex(b : Blob) : Text {
    var s = "";
    for (x in b.vals()) {
      let n = Nat8.toNat(x);
      s #= Char.toText(HEX[n / 16]) # Char.toText(HEX[n % 16]);
    };
    s
  };

  public func sha256(b : Blob) : Blob {
    let d = Sha256.Digest(#sha256);
    d.writeBlob(b);
    d.sum()
  };

  public func sha256Hex(b : Blob) : Text { hex(sha256(b)) };
};
