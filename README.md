# Smart Skin Disease System

Current increment: shared booking, queue, prescriptions and simulated billing.
One Python API saves records locally; the Expo app and Next.js dashboard read
the same database. Supabase integration and secure authentication are pending.

After dependency setup, double-click **Start-API.cmd**, **Start-Dashboard.cmd**
and **Start-Mobile.cmd** in that order. Keep their terminal windows open.
Dashboard: http://127.0.0.1:3000. Open the mobile QR code with Expo Go on Android.
Close each service with Ctrl+C. See SETUP.md and VERIFY.md for exact checks.

Use only synthetic data. Demo identity headers are deliberately selectable and
are not secure authentication. All nine final modules remain planned. Word
editing is deferred at the user's request.

Added care workflow: dashboard /care for assigned doctors and staff; patient Care & bills for shared prescription, dispensing status, itemised bill and confirmed simulated payment. Placeholder items only. New screen/device verification pending; see VERIFY.md. No real payment processing.
