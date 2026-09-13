/// Http.mo — outbound HTTPS from a Thebes smart contract.
///
/// A canister can fetch a URL from the open internet. This is not the same as
/// the IC's `http_request`, and three differences matter:
///
/// 1. **Quorum is per call.** You choose, on each request, how many validators
///    must independently fetch the URL and agree on the result. A cheap read
///    can run at quorum 1 and a settlement oracle at full quorum in the same
///    contract.
/// 2. **Agreement is declared, not programmed.** There is no transform
///    callback to write. Instead the request DECLARES which parts of the
///    response participate in agreement (`withAgreement`): `#bodyOnly`,
///    `#headers [...]`, or `#full`. A real-world endpoint that stamps a
///    `Date` header or a per-request id reaches agreement at any quorum with
///    `#bodyOnly` — no callback ABI, and the declaration is checked at
///    compile time. (`#full`, the default and the v1 behaviour, requires
///    byte-identical responses INCLUDING headers, which only an endpoint you
///    control can promise.)
/// 3. **Submit and read are two messages.** The response is not available in
///    the call that submits it. Submit in one update; read it from a later
///    one. This is the single thing to get right when porting.
///
/// Two API generations live here. The v2 surface (`submitV2` → `Handle` →
/// `pollV2` / `headerValueByName` / `responseHeaders` / `free`) supports
/// several outcalls in flight, response-size bounds, and name-keyed headers;
/// prefer it for all new code — it needs a chain with the outcalls-v2
/// activation armed. The v1 surface (`submit`/`poll`, one response slot,
/// index-only header values) keeps working unchanged.
///
/// Submits are update-only — the runtime rejects them from a query, and so
/// does the compiler. Reading a response (`poll`/`pollV2`, headers) is
/// query-safe.
///
/// The response of a completed outcall lives in update-execution context.
/// Read it from an update call; if you want to serve it from a query
/// afterwards, copy it into stable state in that update first.
import Prim "mo:⛔";

module {
  public type Method = { #get; #post; #head; #put; #delete };

  public type Error = {
    /// The runtime rejected the request — a malformed URL, an unsupported
    /// scheme, a body on a method that forbids one, or a quorum out of range.
    #rejected;
    /// A header was refused; carries the header name.
    #headerRejected : Text;
  };

  public type Response = { status : Nat16; body : Blob };

  public type Poll = { #pending; #ready : Response };

  /// v2 — which parts of the response the validators must agree on.
  ///
  /// * `#full` — status + every header + body (v1 semantics). Sound only for
  ///   an endpoint you control that returns byte-identical responses.
  /// * `#bodyOnly` — status + body; all headers are excluded from agreement
  ///   (and from the delivered response). An endpoint stamping `Date` or a
  ///   request id reaches agreement at any quorum.
  /// * `#headers names` — status + body + exactly these headers (matched
  ///   ASCII-case-insensitively, delivered lowercased, in the order you list
  ///   them). Use it when you need e.g. `content-type` or `etag` attested.
  public type Agreement = { #full; #bodyOnly; #headers : [Text] };

  public type Request = {
    url : Text;
    method : Method;
    body : Blob;
    quorum : Nat32;
    headers : [(Text, Text)];
    /// v2 — refuse a response larger than this many bytes (1 ..= 2 MiB).
    /// The bound is part of the agreement input: an oversize fetch yields a
    /// deterministic refusal (`#tooLarge` from `pollV2`) on every validator.
    maxResponseBytes : Nat;
    /// v2 — the agreement declaration. `#full` for v1-style endpoints.
    agreement : Agreement;
  };

  // Positional method encoding, fixed by the host ABI.
  func methodCode(m : Method) : Nat32 {
    switch m {
      case (#get) 0;
      case (#post) 1;
      case (#head) 2;
      case (#put) 3;
      case (#delete) 4;
    }
  };

  /// Default response-size bound: 2 MiB (the host maximum).
  let defaultMaxResponseBytes : Nat = 2_097_152;

  /// A GET request at quorum 1 with no headers. Refine with the `with*`
  /// helpers before submitting.
  public func get(url : Text) : Request = {
    url; method = #get; body = ""; quorum = 1; headers = [];
    maxResponseBytes = defaultMaxResponseBytes; agreement = #full;
  };

  /// A POST request carrying `body`, quorum 1, no headers.
  public func post(url : Text, body : Blob) : Request = {
    url; method = #post; body; quorum = 1; headers = [];
    maxResponseBytes = defaultMaxResponseBytes; agreement = #full;
  };

  /// A request with an explicit method.
  public func request(url : Text, method : Method) : Request = {
    url; method; body = ""; quorum = 1; headers = [];
    maxResponseBytes = defaultMaxResponseBytes; agreement = #full;
  };

  /// Set how many validators must independently fetch and agree. Higher
  /// quorum costs more and buys more assurance; choose it per call.
  public func withQuorum(r : Request, quorum : Nat32) : Request = { r with quorum };

  /// Set the request body.
  public func withBody(r : Request, body : Blob) : Request = { r with body };

  /// v2 — declare which parts of the response participate in agreement.
  /// The one to reach for against real third-party APIs: `#bodyOnly` (or
  /// `#headers` naming the ones you need) lets a `Date`-stamping endpoint
  /// agree at quorum 4.
  public func withAgreement(r : Request, agreement : Agreement) : Request = {
    r with agreement
  };

  /// v2 — bound the response size (1 ..= 2 MiB). An oversize response is
  /// refused deterministically on every validator (`#tooLarge`).
  public func withMaxResponseBytes(r : Request, maxResponseBytes : Nat) : Request = {
    r with maxResponseBytes
  };

  /// Append a request header.
  public func withHeader(r : Request, name : Text, value : Text) : Request = {
    r with headers = Prim.Array_tabulate<(Text, Text)>(
      r.headers.size() + 1,
      func i = if (i < r.headers.size()) r.headers[i] else (name, value))
  };

  /// Submit the request. Returns once it is queued — not once it has
  /// completed. Read the response from a later update with `poll`.
  ///
  /// Update-only: calling this from a query is a compile-time error.
  public func submit(r : Request) : { #ok; #err : Error } {
    // Submit FIRST: the host attaches `addHeader` calls to the most
    // recently submitted request. (Adding before submitting attached the
    // headers to an earlier in-flight request, or failed outright when
    // none existed — the v1 ordering bug.)
    let rc = Prim.thebesHttpRequestSubmit(
      Prim.encodeUtf8(r.url), methodCode(r.method), r.body, r.quorum);
    if (rc != 0) return #err(#rejected);
    for ((name, value) in r.headers.values()) {
      let hrc = Prim.thebesHttpRequestAddHeader(
        Prim.encodeUtf8(name), Prim.encodeUtf8(value));
      if (hrc != 0) return #err(#headerRejected(name));
    };
    #ok
  };

  /// Whether the outcall submitted earlier has landed. Returns `#pending`
  /// until a response is available, then `#ready`.
  public func poll() : Poll {
    let st = Prim.thebesHttpResponseStatus();
    if (st < 0) return #pending;
    #ready({
      status = Prim.intToNat16Wrap(Prim.int32ToInt(st));
      body = Prim.thebesHttpResponseBodyCopy();
    })
  };

  /// The response body as UTF-8 text, or `null` if it is not valid UTF-8.
  public func text(r : Response) : ?Text = Prim.decodeUtf8(r.body);

  /// The number of headers on the response.
  public func headerCount() : Nat32 = Prim.thebesHttpResponseHeaderCount();

  /// The header VALUE at `idx`, or `null` when the index is out of range or
  /// the value is not valid UTF-8.
  ///
  /// Header values are addressable by index only: the host exposes no
  /// accessor for header *names*, so a value cannot be looked up by name.
  /// If you need a specific header, request an endpoint that returns it in
  /// the body, or read values by position when their order is known.
  public func headerValue(idx : Nat32) : ?Text {
    let size = Prim.thebesHttpResponseHeaderValueSize(idx);
    if (size < 0) return null;
    Prim.decodeUtf8(Prim.thebesHttpResponseHeaderValueCopy(idx))
  };

  // ════════════════════════════════════════════════════════════════════
  // v2 — handles, agreement, bounded responses, name-keyed headers.
  //
  // `submitV2` returns a Handle; every read takes it, so several outcalls
  // can be in flight at once and a stale read is an explicit
  // `#unknownHandle`, never another request's bytes. Requires a chain on
  // which the outcalls-v2 activation height is armed (`#notActive`
  // otherwise).
  // ════════════════════════════════════════════════════════════════════

  /// An outcall in flight (or delivered). Opaque; obtain it from `submitV2`.
  public type Handle = Int64;

  public type SubmitError = {
    /// The runtime rejected the request (malformed URL/scheme, quorum or
    /// size bound out of range, too many headers).
    #rejected;
    /// The outcalls-v2 activation height is not armed (or not yet reached)
    /// on this chain.
    #notActive;
    /// Too many outcalls already in flight from this canister.
    #tooManyInFlight;
  };

  public type PollV2 = {
    #pending;
    #ready : Response;
    /// The handle was never issued, was freed, or its slot was evicted.
    #unknownHandle;
    /// The response exceeded `maxResponseBytes` — refused identically on
    /// every validator (the refusal itself is quorum-agreed).
    #tooLarge;
  };

  // ── request encoding (host codec v2; layout owned by the host's
  //    decode_submit_v2 — version(1)=2, method(1), quorum(1), mode(1),
  //    maxResponseBytes be64, url, request headers, allow-list, body; all
  //    lengths be32) ──

  func be32(n : Nat) : [Nat8] = [
    Prim.natToNat8((n / 16_777_216) % 256),
    Prim.natToNat8((n / 65_536) % 256),
    Prim.natToNat8((n / 256) % 256),
    Prim.natToNat8(n % 256),
  ];

  func be64(n : Nat) : [Nat8] = [
    Prim.natToNat8((n / 72_057_594_037_927_936) % 256),
    Prim.natToNat8((n / 281_474_976_710_656) % 256),
    Prim.natToNat8((n / 1_099_511_627_776) % 256),
    Prim.natToNat8((n / 4_294_967_296) % 256),
    Prim.natToNat8((n / 16_777_216) % 256),
    Prim.natToNat8((n / 65_536) % 256),
    Prim.natToNat8((n / 256) % 256),
    Prim.natToNat8(n % 256),
  ];

  func lenPrefixed(b : [Nat8]) : [[Nat8]] = [be32(b.size()), b];

  func textBytes(t : Text) : [Nat8] = Prim.blobToArray(Prim.encodeUtf8(t));

  func concatBytes(chunks : [[Nat8]]) : [Nat8] {
    var total = 0;
    for (c in chunks.values()) { total += c.size() };
    let out = Prim.Array_init<Nat8>(total, 0);
    var i = 0;
    for (c in chunks.values()) {
      for (b in c.values()) { out[i] := b; i += 1 };
    };
    Prim.Array_tabulate<Nat8>(total, func j = out[j])
  };

  func encodeRequestV2(r : Request) : Blob {
    let (mode, allow) : (Nat8, [Text]) = switch (r.agreement) {
      case (#full) (0, []);
      case (#bodyOnly) (1, []);
      case (#headers names) (2, names);
    };
    var chunks : [[Nat8]] = [[
      2 : Nat8,
      Prim.natToNat8(Prim.nat32ToNat(methodCode(r.method)) % 256),
      Prim.natToNat8(Prim.nat32ToNat(r.quorum) % 256),
      mode,
    ]];
    func push(c : [Nat8]) {
      chunks := Prim.Array_tabulate<[Nat8]>(
        chunks.size() + 1,
        func i = if (i < chunks.size()) chunks[i] else c);
    };
    push(be64(r.maxResponseBytes));
    for (c in lenPrefixed(textBytes(r.url)).values()) push(c);
    push(be32(r.headers.size()));
    for ((name, value) in r.headers.values()) {
      for (c in lenPrefixed(textBytes(name)).values()) push(c);
      for (c in lenPrefixed(textBytes(value)).values()) push(c);
    };
    push(be32(allow.size()));
    for (name in allow.values()) {
      for (c in lenPrefixed(textBytes(name)).values()) push(c);
    };
    for (c in lenPrefixed(Prim.blobToArray(r.body)).values()) push(c);
    Prim.arrayToBlob(concatBytes(chunks))
  };

  /// v2 submit. Returns a `Handle` to poll with `pollV2`; the response
  /// arrives in a LATER message, exactly like v1.
  ///
  /// Update-only: calling this from a query is a compile-time error.
  public func submitV2(r : Request) : { #ok : Handle; #err : SubmitError } {
    // Host codec carries quorum in one byte; refuse what cannot encode.
    if (r.quorum == 0 or Prim.nat32ToNat(r.quorum) > 255) return #err(#rejected);
    let h = Prim.thebesHttpRequestSubmitV2(encodeRequestV2(r));
    if (Prim.int64ToInt(h) > 0) return #ok(h);
    switch (Prim.int64ToInt(h)) {
      case (-2) #err(#notActive);
      case (-3) #err(#tooManyInFlight);
      case _ #err(#rejected);
    }
  };

  /// Poll an outcall by handle.
  public func pollV2(h : Handle) : PollV2 {
    let st = Prim.thebesHttpResponseStatusV2(h);
    let sti = Prim.int32ToInt(st);
    if (sti == -1) return #pending;
    if (sti < 0) return #unknownHandle;
    if (sti == 0) return #tooLarge;
    #ready({
      status = Prim.intToNat16Wrap(sti);
      body = Prim.thebesHttpResponseBodyCopyV2(h);
    })
  };

  /// v2 — a response header VALUE looked up by NAME (ASCII-case-
  /// insensitive; first match). `null` when the handle is unknown, the
  /// response is pending, the header is absent, or the value is not UTF-8.
  ///
  /// Only headers inside the agreement (`#full` or listed in `#headers`)
  /// are delivered — `#bodyOnly` responses have none.
  public func headerValueByName(h : Handle, name : Text) : ?Text {
    let nameBlob = Prim.encodeUtf8(name);
    let size = Prim.thebesHttpResponseHeaderValueSizeByName(h, nameBlob);
    if (Prim.int64ToInt(size) < 0) return null;
    Prim.decodeUtf8(Prim.thebesHttpResponseHeaderValueCopyByName(h, nameBlob))
  };

  /// v2 — all delivered (agreed) response headers as (name, value) pairs.
  /// Empty when the handle is unknown or the response is pending.
  public func responseHeaders(h : Handle) : [(Text, Text)] {
    let n = Prim.int32ToInt(Prim.thebesHttpResponseHeaderCountV2(h));
    if (n <= 0) return [];
    Prim.Array_tabulate<(Text, Text)>(Prim.abs(n), func i {
      let idx = Prim.natToNat32(i);
      let name = switch (Prim.decodeUtf8(Prim.thebesHttpResponseHeaderNameCopyV2(h, idx))) {
        case (?t) t; case null "";
      };
      let value = switch (Prim.decodeUtf8(Prim.thebesHttpResponseHeaderValueCopyV2(h, idx))) {
        case (?t) t; case null "";
      };
      (name, value)
    })
  };

  /// v2 — release a delivered response slot. Returns false when the handle
  /// is unknown or still pending. Update-only.
  public func free(h : Handle) : Bool {
    Prim.int64ToInt(Prim.thebesHttpResponseFree(h)) == 0
  };
}
