# Install the DI middleware on startup, on every broker

`setup_di` does not call `add_middleware`; it registers an `on_startup` hook that walks
`app.brokers` and adds the middleware factory to every broker not already carrying it. A FastStream
0.7 app holds a list of brokers and `app.broker` is only `brokers[0]`, so installing at `setup_di`
time left every other broker without DI, and the gap stayed silent until the first message failed
inside `FromDI` ([#42](https://github.com/modern-python/modern-di-faststream/issues/42)). Iterating
`app.brokers` inside `setup_di` fixes only the construction-time case and leaves a documented
ordering rule for the rest; startup is the one moment when the list is complete and no message has
been consumed, and a late install still applies because FastStream builds a subscriber's middleware
stack per message from the broker config. The membership check reads `broker.config.broker_middlewares`, the same
sequence FastStream builds from, so a restarted app does not install a second copy.
[#56](https://github.com/modern-python/modern-di-faststream/issues/56) then dropped the
`if not app.broker` guard, so a broker created in a user hook registered before `setup_di` is
covered too.
