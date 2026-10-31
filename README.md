# 다온 클래스 (단일 파일 버전)

## 실행 방법
```bash
pip install -r requirements.txt
python main.py
```

브라우저에서 http://localhost:5000 접속

## 첫 회원가입
처음 가입하는 계정이 자동으로 관리자가 됩니다.

## Render 배포
1. GitHub에 main.py + requirements.txt 올리기
2. Render → New Web Service
3. Build: `pip install -r requirements.txt`
4. Start: `gunicorn main:app`
