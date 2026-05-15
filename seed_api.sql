INSERT INTO tenants (
  tenant_id,
  tenant_display_name,
  plan
)
VALUES (
  'bank-a',
  'Bank A 고객센터',
  'paid'
);

-- 비밀번호 1234용 hash는 API 회원가입 후 직접 paid로 승격하는 방식 권장
-- 예시:
-- UPDATE users
-- SET user_type='paid', tenant_id='bank-a', display_name='유료 고객'
-- WHERE email='paid@bank-a.com';
