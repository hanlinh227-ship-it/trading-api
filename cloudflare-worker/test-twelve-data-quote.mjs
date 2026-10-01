import assert from 'node:assert/strict';
import {handleTwelveDataReferenceQuote, TWELVE_DATA_FOREX_PAIRS} from './twelve-data-quote.mjs';

const now = Date.parse('2026-10-01T12:00:00Z');
const env = {TWELVE_DATA_API_KEY: 'test-secret'};
const req = (url, init) => new Request(`https://worker.test${url}`, init);
const makeFetch = (body, status = 200) => async (url, init) => {
  assert.equal(new URL(url).origin, 'https://api.twelvedata.com');
  assert.equal(new URL(url).pathname, '/quote');
  assert.equal(new URL(url).searchParams.get('apikey'), 'test-secret');
  assert.equal(init.method, 'GET');
  return Response.json(body, {status});
};

assert.equal(TWELVE_DATA_FOREX_PAIRS.length, 28);
assert.equal(new Set(TWELVE_DATA_FOREX_PAIRS).size, 28);
{
  let calls = 0;
  const response = await handleTwelveDataReferenceQuote(req('/market/forex/quotes'), env, {
    now: () => now,
    fetchImpl: async url => {
      calls++;
      const symbol = new URL(url).searchParams.get('symbol');
      return Response.json({symbol,close:'1.12345',timestamp:now/1000-0.5});
    },
  });
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.equal(calls, 28);
  assert.equal(body.requested, 28);
  assert.equal(body.received, 28);
  assert.equal(body.complete, true);
  assert.equal(body.executionAuthoritative, false);
}
{
  const response = await handleTwelveDataReferenceQuote(req('/market/forex/quote?symbol=EURUSD'), env, {
    now: () => now,
    fetchImpl: makeFetch({symbol: 'EUR/USD', close: '1.12345', timestamp: now / 1000 - 0.5}),
  });
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.equal(body.price, 1.12345);
  assert.equal(body.source, 'TWELVE_DATA');
  assert.equal(body.dataType, 'REFERENCE_PRICE');
  assert.equal(body.executionAuthoritative, false);
  assert.equal(body.ageMs, 500);
  assert.equal(body.sourceTimestamp, '2026-10-01T11:59:59.500Z');
}
{
  const response = await handleTwelveDataReferenceQuote(req('/market/forex/quote?symbol=EUR%2FUSD'), env, {
    now: () => now,
    fetchImpl: makeFetch({symbol: 'EUR/USD', close: '1.12345', timestamp: now / 1000 - 66}),
  });
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.equal(body.error, 'DATA_BLOCK');
  assert.equal('price' in body, false);
}
{
  const response = await handleTwelveDataReferenceQuote(req('/market/forex/quote?symbol=USDMXN'), env);
  assert.equal(response.status, 400);
}
{
  const response = await handleTwelveDataReferenceQuote(req('/market/forex/quote?symbol=EURUSD'), {});
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error, 'TWELVE_DATA_CONFIGURATION_MISSING');
}
{
  const response = await handleTwelveDataReferenceQuote(req('/market/forex/quote?symbol=EURUSD', {method: 'POST'}), env);
  assert.equal(response.status, 405);
}
{
  const response = await handleTwelveDataReferenceQuote(req('/market/forex/quote?symbol=EURUSD'), env, {
    now: () => now,
    fetchImpl: makeFetch({symbol: 'GBP/USD', close: '1.12345', timestamp: now / 1000}),
  });
  assert.equal(response.status, 502);
  assert.equal((await response.json()).error, 'TWELVE_DATA_SYMBOL_OR_RESPONSE_MISMATCH');
}
console.log('TWELVE_DATA_READONLY_QUOTE_TESTS=PASS');
