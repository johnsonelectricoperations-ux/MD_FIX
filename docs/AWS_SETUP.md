# 배포 가이드: 한국투자증권 API + 텔레그램 + AWS EC2

순서대로 따라 하면 됩니다. **1~3단계는 회원님 PC에서, 4단계만 AWS에서** 진행합니다.
막히는 부분은 화면 내용을 AI에게 붙여넣고 물어보세요.

## 1단계: 한국투자증권 KIS Developers 신청 (약 10분)

1. https://apiportal.koreainvestment.com 접속 → 회원가입 (증권 계좌 ID로)
2. 상단 메뉴 **API 신청** → 개인 → 약관 동의 → 신청
3. **모의투자 신청**: 한국투자증권 홈페이지/앱에서 "모의투자" 참가 신청
   (모의투자 계좌번호가 발급됩니다)
4. KIS Developers 마이페이지에서 **앱키(App Key)·앱시크릿(App Secret)** 확인
   - 실전투자용과 모의투자용 키가 **따로** 발급됩니다. 모의투자용을 사용하세요.
5. 발급받은 값을 `.env`에 기록 (아래 3단계 참고). **절대 카톡·메모앱에
   저장하거나 git에 커밋하지 마세요.**

## 2단계: 텔레그램 봇 만들기 (약 5분)

1. 텔레그램에서 `@BotFather` 검색 → `/newbot` → 봇 이름 입력
   → **봇 토큰**을 받습니다 (`123456:ABC-...` 형태)
2. 만들어진 봇과 대화방을 열고 아무 메시지나 한 번 보냅니다
3. 브라우저에서 `https://api.telegram.org/bot<봇토큰>/getUpdates` 접속
   → 응답에서 `"chat":{"id":123456789...` 의 숫자가 **chat_id**입니다

## 3단계: PC에서 로컬 테스트

프로젝트 폴더에 `.env` 파일 생성 (`.env.example` 복사 후 수정):

```
KIS_APP_KEY=발급받은앱키
KIS_APP_SECRET=발급받은앱시크릿
KIS_ACCOUNT_NO=모의계좌번호-01
KIS_MODE=paper
TELEGRAM_BOT_TOKEN=봇토큰
TELEGRAM_CHAT_ID=챗아이디
```

테스트 순서 (반드시 이 순서대로):

```powershell
py -m pip install -r requirements.txt
py scripts\daily_signal.py              # ① 신호·계획만 출력 (주문 없음)
py scripts\daily_signal.py --execute    # ② 모의투자 계좌에 실제 주문
```

①에서 계좌 조회와 목표 비중이 정상 출력되는지, 텔레그램 메시지가
도착하는지 확인한 뒤 ②를 실행하세요. ②는 모의투자 계좌라 실제 돈이
움직이지 않습니다.

## 4단계: AWS EC2 설정

1. **인스턴스 생성**: AWS 콘솔 → EC2 → 리전 **서울(ap-northeast-2)** →
   Launch Instance → Ubuntu Server 24.04 LTS, **t2.micro 또는 t3.micro
   (프리티어)** → 키페어 새로 생성(.pem 파일 안전하게 보관) → 보안 그룹은
   SSH(22)만, 소스는 "내 IP" → 시작
2. **접속**: `ssh -i 키페어.pem ubuntu@<인스턴스 퍼블릭 IP>`
3. **기본 설정**:

```bash
sudo timedatectl set-timezone Asia/Seoul   # cron을 KST 기준으로
sudo apt update && sudo apt install -y python3-venv git
git clone -b STOCK-RULE https://github.com/johnsonelectricoperations-ux/MD_FIX.git
cd MD_FIX
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
nano .env        # 3단계와 같은 내용 입력 후 저장
chmod 600 .env   # 소유자만 읽기 가능
mkdir -p logs
```

4. **수동 실행으로 검증**:

```bash
.venv/bin/python scripts/daily_signal.py
```

5. **cron 등록** (평일 15:15 KST 자동 실행):

```bash
crontab -e
# 파일 맨 아래에 추가:
15 15 * * 1-5 cd /home/ubuntu/MD_FIX && .venv/bin/python scripts/daily_signal.py --execute >> logs/daily.log 2>&1
```

6. **동작 확인**: 다음 거래일 15:15 이후 텔레그램 메시지가 오는지 확인.
   문제가 있으면 `cat logs/daily.log`의 내용을 AI에게 붙여넣으세요.

## 운영 참고

- **공휴일**: 장이 열리지 않는 날은 주문이 거부될 뿐 문제없습니다.
  거부 내용도 텔레그램으로 통지됩니다.
- **코드 업데이트**: EC2에서 `cd MD_FIX && git pull`
- **비용**: 프리티어는 12개월 무료. 이후 t3.micro 기준 월 1~2만 원 수준이니
  만료 시점을 달력에 표시해 두세요.

## 실거래 시작 절차 (D-013: 관찰 1주 → 주문 개시)

실거래는 모의투자와 달리 **실전투자용 앱키**와 실계좌번호를 사용합니다.
`.env`를 다음과 같이 설정하세요:

```
KIS_APP_KEY=실전투자용앱키
KIS_APP_SECRET=실전투자용앱시크릿
KIS_ACCOUNT_NO=실계좌번호-01
KIS_MODE=live
MAX_ORDER_VALUE_KRW=6000000   # 매수 1건 한도 (투입금 500만원 기준)
DAILY_LOSS_LIMIT_PCT=15       # 계좌가 하루 새 15% 넘게 줄면 신규 매수 차단
```

**1주차 (관찰 모드)**: cron에 `--execute`를 **넣지 않습니다**. 매일 15:15에
잔고 조회와 주문 계획만 텔레그램으로 옵니다. 1주간 확인할 것:
- 계좌 총평가·예수금 금액이 HTS/앱과 일치하는가
- 주문 계획(종목·수량)이 상식적인가 (총평가를 넘는 수량이 나오면 즉시 중단)

```
15 15 * * 1-5 cd /home/ubuntu/MD_FIX && .venv/bin/python scripts/daily_signal.py >> logs/daily.log 2>&1
```

**2주차부터 (주문 개시)**: 1주간 이상이 없으면 cron 명령에
`--execute --live`를 추가합니다 (`KIS_MODE=live`와 `--live` 둘 다 있어야
실주문이 나갑니다):

```
15 15 * * 1-5 cd /home/ubuntu/MD_FIX && .venv/bin/python scripts/daily_signal.py --execute --live >> logs/daily.log 2>&1
```

**안전장치 동작**: 매수 1건이 `MAX_ORDER_VALUE_KRW`를 넘으면 그 주문만
차단되고 텔레그램으로 통지됩니다. 계좌 평가액이 직전 실행 대비
`DAILY_LOSS_LIMIT_PCT` 이상 하락하면 신규 매수가 전부 차단됩니다 (매도,
즉 현금 대피는 어떤 경우에도 차단되지 않습니다). 킬 스위치 해제는 원인
확인 후 `data/account_state.json` 삭제 또는 다음 정상 실행으로 자동 갱신.
