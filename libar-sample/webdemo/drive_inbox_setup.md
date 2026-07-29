# 드라이브 자동 업로드 수신함 설정 (5분, 1회)

앱에서 "학습용 조각 제공"에 동의하면 스캔마다 zip이 **팀 공유 드라이브 폴더로 자동 업로드**되게 하는
수신함(Apps Script)입니다. 아인 구글 계정으로 아래 순서대로 하면 됩니다.

## 1. 수신 폴더 ✅ 완료
팀 공유 폴더 사용: `1_FwIjOTMtsW_8cBmfPCIeG4bYQiFhMFT` (아래 코드에 반영됨)

## 2. Apps Script 만들기
[script.google.com](https://script.google.com) → 새 프로젝트 → 아래 코드 통째로 붙여넣기:

```javascript
const FOLDER_ID = '1_FwIjOTMtsW_8cBmfPCIeG4bYQiFhMFT';

function doPost(e) {
  const data = JSON.parse(e.postData.contents);
  const bytes = Utilities.base64Decode(data.zip);
  const blob = Utilities.newBlob(bytes, 'application/zip', data.name || 'libar_crops.zip');
  DriveApp.getFolderById(FOLDER_ID).createFile(blob);
  return ContentService.createTextOutput('ok');
}
```

## 3. 웹앱으로 배포
우상단 **배포 → 새 배포 → 유형: 웹 앱**
- 실행 계정: **나(아인)**  ← 업로더가 로그인 없이도 폴더에 저장되는 이유
- 액세스 권한: **모든 사용자**
- 배포 → 권한 승인(내 계정 선택, 고급 → 이동 → 허용) → **웹 앱 URL 복사**
  (`https://script.google.com/macros/s/XXXX/exec` 형태)

## 4. 앱에 URL 연결
복사한 URL을 저(Claude)에게 주면 `UPLOAD_URL`에 넣어 재배포합니다.

## 동작 확인
데모 앱에서 판정 시연 → 📦 동의 → 1~2분 내 공유 드라이브 `LibAR_조각수집`에
`libar_crops_....zip`이 생기면 성공.

## 참고
- 업로드 내용: 라벨 조각 jpg + manifest.json(정답 청구기호) — 서가 전체 사진 없음
- URL을 아는 사람만 업로드 가능(다운로드·열람은 불가). 유출 시 배포 삭제로 즉시 차단
- Apps Script 무료 한도: 하루 수천 건 — 팀 테스트 규모에 충분
