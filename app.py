<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ورود به سامانه</title>
    <link href="https://cdn.jsdelivr.net/npm/daisyui@4.4.20/dist/full.min.css" rel="stylesheet" />
    <link href="https://cdn.jsdelivr.net/npm/@fontsource/vazirmatn@latest/index.css" rel="stylesheet" />
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {
            font-family: Vazirmatn, sans-serif;
            background-color: #f0f2f5;
        }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen">
    <div class="bg-white p-6 rounded-lg shadow-md w-full max-w-md text-center">
        <h1 class="text-xl font-semibold mb-6">لطفاً کدملی خود را وارد کنید</h1>
        <input type="text" id="national_id" placeholder="مثال: 1234567890" class="input input-bordered w-full mb-4 text-center" dir="ltr" maxlength="10">
        <button onclick="startLogin()" class="btn btn-primary w-full">دریافت کد تأیید</button>
    </div>
    <dialog id="message_modal" class="modal">
        <div class="modal-box text-center">
            <h3 id="modal_title" class="font-bold text-lg"></h3>
            <p id="modal_message" class="py-4"></p>
            <div class="modal-action justify-center">
                <form method="dialog"><button id="modal_button" class="btn">بستن</button></form>
            </div>
        </div>
    </dialog>
    <dialog id="otp_modal" class="modal">
        <div class="modal-box text-center">
            <h3 class="font-bold text-lg">ورود با کد تأیید</h3>
            <div class="flex justify-center gap-2 mb-4">
                <input type="text" id="otp_digit_1" class="input input-bordered w-12 text-center" maxlength="1" dir="ltr">
                <input type="text" id="otp_digit_2" class="input input-bordered w-12 text-center" maxlength="1" dir="ltr">
                <input type="text" id="otp_digit_3" class="input input-bordered w-12 text-center" maxlength="1" dir="ltr">
                <input type="text" id="otp_digit_4" class="input input-bordered w-12 text-center" maxlength="1" dir="ltr">
                <input type="text" id="otp_digit_5" class="input input-bordered w-12 text-center" maxlength="1" dir="ltr">
            </div>
            <button onclick="verifyOtp()" class="btn btn-primary w-full">تأیید</button>
            <div class="modal-action">
                <form method="dialog"><button class="btn btn-ghost">انصراف</button></form>
            </div>
        </div>
    </dialog>
    <script>
        const API_BACKEND_URL = "https://tavonibot.onrender.com";

        function showModal(title, message, isSuccess) {
            const modal = document.getElementById('message_modal');
            document.getElementById('modal_title').textContent = title;
            document.getElementById('modal_message').textContent = message;
            const modalButton = document.getElementById('modal_button');
            modalButton.className = 'btn';
            if (isSuccess) modalButton.classList.add('btn-success');
            else modalButton.classList.add('btn-error');
            modal.showModal();
        }

        async function startLogin() {
            const national_id = document.getElementById('national_id').value;
            if (!national_id) return showModal('خطا', 'کد ملی را وارد کنید.', false);
            try {
                const response = await fetch(`${API_BACKEND_URL}/api/start-login`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({national_id})
                });
                const result = await response.json();
                if (response.ok) {
                    document.getElementById('otp_modal').showModal();
                    // فوکوس روی اولین باکس
                    document.getElementById('otp_digit_1').focus();
                } else showModal('خطا', result.error, false);
            } catch (e) {showModal('خطا', 'ارتباط با سرور برقرار نشد.', false);}
        }

        function getOtpCode() {
            return [
                document.getElementById('otp_digit_1').value,
                document.getElementById('otp_digit_2').value,
                document.getElementById('otp_digit_3').value,
                document.getElementById('otp_digit_4').value,
                document.getElementById('otp_digit_5').value
            ].join('');
        }

        // جابه‌جایی خودکار بین باکس‌ها
        const otpInputs = ['otp_digit_1', 'otp_digit_2', 'otp_digit_3', 'otp_digit_4', 'otp_digit_5'];
        otpInputs.forEach((id, index) => {
            const input = document.getElementById(id);
            input.addEventListener('input', function(e) {
                if (this.value.length === this.maxLength) {
                    const nextInput = document.getElementById(otpInputs[index + 1]);
                    if (nextInput) nextInput.focus();
                }
            });
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Backspace' && !this.value && index > 0) {
                    document.getElementById(otpInputs[index - 1]).focus();
                }
            });
        });

        async function verifyOtp() {
            const national_id = document.getElementById('national_id').value;
            const otp_code = getOtpCode();
            if (otp_code.length !== 5 || !/^\d+$/.test(otp_code)) return showModal('خطا', 'کد تأیید باید ۵ رقم باشد.', false);
            try {
                const response = await fetch(`${API_BACKEND_URL}/api/verify-otp`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({national_id, otp_code})
                });
                const result = await response.json();
                if (response.ok) {
                    if (result.action === 'go_to_profile') window.location.href = `profile.html?nid=${national_id}`;
                    else if (result.action === 'go_to_dashboard') window.location.href = `dashboard.html?nid=${national_id}`;
                } else showModal('خطا', result.error, false);
                document.getElementById('otp_modal').close();
            } catch (e) {showModal('خطا', 'ارتباط با سرور برقرار نشد.', false);}
        }
    </script>
</body>
</html>