@echo off
echo ========================================
echo Cloud Build サービスアカウントの権限を設定
echo ========================================
echo.

REM プロジェクトIDを入力
set /p PROJECT_ID="Google CloudのプロジェクトID (例: gen-lang-client-0553940805): "

echo.
echo プロジェクトを設定中...
gcloud config set project %PROJECT_ID%

echo.
echo プロジェクト番号を取得中...
for /f "tokens=*" %%i in ('gcloud projects describe %PROJECT_ID% --format="value(projectNumber)"') do set PROJECT_NUMBER=%%i

echo プロジェクト番号: %PROJECT_NUMBER%
echo.

echo Cloud Build サービスアカウントに権限を付与中...
echo.

echo [1/4] Cloud Run 管理者権限を付与...
gcloud projects add-iam-policy-binding %PROJECT_ID% ^
  --member="serviceAccount:%PROJECT_NUMBER%@cloudbuild.gserviceaccount.com" ^
  --role="roles/run.admin"

echo [2/4] サービスアカウントユーザー権限を付与...
gcloud projects add-iam-policy-binding %PROJECT_ID% ^
  --member="serviceAccount:%PROJECT_NUMBER%@cloudbuild.gserviceaccount.com" ^
  --role="roles/iam.serviceAccountUser"

echo [3/4] Service Usage Consumer権限を付与...
gcloud projects add-iam-policy-binding %PROJECT_ID% ^
  --member="serviceAccount:%PROJECT_NUMBER%@cloudbuild.gserviceaccount.com" ^
  --role="roles/serviceusage.serviceUsageConsumer"

echo [4/4] Cloud Build サービスアカウント権限を付与...
gcloud projects add-iam-policy-binding %PROJECT_ID% ^
  --member="serviceAccount:%PROJECT_NUMBER%@cloudbuild.gserviceaccount.com" ^
  --role="roles/cloudbuild.builds.builder"

echo.
echo ========================================
echo 権限の設定が完了しました！
echo ========================================
echo.
echo 次のステップ:
echo 1. GitHubのActionsページを開く
echo 2. 失敗したワークフローの「Re-run all jobs」をクリック
echo.
echo GitHub Actions: https://github.com/ryom080502-dev/audioGIJI6/actions
echo.
pause
