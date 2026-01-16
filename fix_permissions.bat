@echo off
echo ========================================
echo サービスアカウントの権限を修正
echo ========================================
echo.

REM プロジェクトIDを入力
set /p PROJECT_ID=gen-lang-client-0553940805

echo.
echo プロジェクトを設定中...
gcloud config set project %PROJECT_ID%

echo.
echo 必要な権限を追加中...
echo.

echo [1/5] Cloud Run 管理者権限を付与...
gcloud projects add-iam-policy-binding %PROJECT_ID% ^
  --member="serviceAccount:github-actions@%PROJECT_ID%.iam.gserviceaccount.com" ^
  --role="roles/run.admin"

echo [2/5] ストレージ管理者権限を付与...
gcloud projects add-iam-policy-binding %PROJECT_ID% ^
  --member="serviceAccount:github-actions@%PROJECT_ID%.iam.gserviceaccount.com" ^
  --role="roles/storage.admin"

echo [3/5] サービスアカウントユーザー権限を付与...
gcloud projects add-iam-policy-binding %PROJECT_ID% ^
  --member="serviceAccount:github-actions@%PROJECT_ID%.iam.gserviceaccount.com" ^
  --role="roles/iam.serviceAccountUser"

echo [4/5] Cloud Build エディター権限を付与...
gcloud projects add-iam-policy-binding %PROJECT_ID% ^
  --member="serviceAccount:github-actions@%PROJECT_ID%.iam.gserviceaccount.com" ^
  --role="roles/cloudbuild.builds.editor"

echo [5/5] Artifact Registry 管理者権限を付与...
gcloud projects add-iam-policy-binding %PROJECT_ID% ^
  --member="serviceAccount:github-actions@%PROJECT_ID%.iam.gserviceaccount.com" ^
  --role="roles/artifactregistry.admin"

echo.
echo ========================================
echo 権限の追加が完了しました！
echo ========================================
echo.
echo 次のステップ:
echo 1. GitHubリポジトリを開く
echo 2. Actions タブを開く
echo 3. 失敗したワークフローの右上にある「Re-run jobs」をクリック
echo.
pause
