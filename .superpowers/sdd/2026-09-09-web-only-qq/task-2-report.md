# Task 2 report: Web QQ sign-in and Mini retirement

## Result

- Replaced automatic WeChat QR creation, polling, confirmation and exchange with one explicit QQ login action.
- The Web client accepts only `https://graph.qq.com/oauth2.0/authorize` with no credentials, fragment, alternate port or path variant before navigation.
- QQ callback errors use a fixed public enum map. Only `loginError` is removed from the current URL; route, other query parameters and fragment remain.
- `/me`, HttpOnly Web session, CSRF logout and nonproduction test Web login remain. Optional QQ avatars accept only HTTPS `q.qlogo.cn` or `thirdqq.qlogo.cn`; the separate saved `avatarDataUrl` endpoint remains available as fallback.
- H5 has one inert Taro entry page. The entry graph no longer mounts or imports Mini product pages or promotion UI. Direct WeApp config/build/dev/refresh attempts fail with an explicit retirement message.
- Active help, conversation deletion, SimC and session-expiry copy now describe QQ/Web behavior and the no-migration policy.

## TDD evidence

- RED: 5 expected failures across the new QQ URL guard, QQ avatar guard, QQ login client and callback error tests before implementation.
- GREEN: targeted QQ domain/API/model tests passed 27/27 after implementation; the final selected frontend suite passed 252/252 across 32 files.
- Replaced `web-login-home.test.tsx` and `web-auth-model.test.ts` to cover the QQ flow. Removed one obsolete Mini promotion interaction case from `web-shell-stream.test.tsx` and updated static Web shell/boundary contracts.

## Retired tests excluded from active selection

- `apps/mini-taro/src/features/auth/mini-account-avatar.test.tsx`
- `apps/mini-taro/src/features/auth/mini-session.test.ts`
- `apps/mini-taro/src/features/auth/mini-test-login-lifecycle.test.tsx`
- `apps/mini-taro/src/features/help/mini-help.test.tsx`
- `apps/mini-taro/src/features/theme/mini-theme.test.ts`
- `apps/mini-taro/src/features/theme/mini-theme-picker.test.tsx`
- `apps/mini-taro/src/pages/auth/web-login-avatar.test.tsx`
- `apps/mini-taro/src/pages/auth/web-login-confirm.test.ts`
- `apps/mini-taro/src/pages/chickenbro/index.test.ts`
- `apps/mini-taro/src/pages/chickenbro/history-interactions.test.tsx`
- `apps/mini-taro/src/pages/simc/index.test.ts`
- `apps/mini-taro/src/pages/simc/task-detail.test.ts`
- `apps/mini-taro/src/pages/simc/tasks.test.ts`
- `apps/mini-taro/src/pages/simc/mini-task-id.test.tsx`

The historical Mini source and its tests remain recoverable in Git; they are outside the active typecheck/test/build graph.

## Verification

- `npm run test:taro`: 252/252 passed, 32/32 files.
- `npm run typecheck`: passed.
- `npm run lint`: passed with zero warnings.
- `node --test tests/retained-client-boundary.test.js`: 7/7 passed.
- `env -u WOW_TEST_LOGIN_UI NODE_ENV=production npm run build:h5`: passed.
- Production artifact scan: zero `/auth/wechat`, `qrDataUrl`, `WebMiniProgramPromo`, Mini confirmation page, WeChat QR login or retry strings; QQ endpoint, official host and official logo URL are present.
- `npm run build:weapp`: expected exit 1 with the retired-product message.
- Direct `TARO_ENV=weapp` config load: expected exit 1 with the retired-product message.

## Limitations

- Browser preview and direct `/` and `/simc` route verification are assigned to the controller.
- Real QQ authorization is not verified locally and remains dependent on QQ application review and later environment-backed acceptance.
- The production H5 build retains existing size warnings: 528 KiB mascot, 407 KiB app JavaScript and 628 KiB combined entrypoint.
