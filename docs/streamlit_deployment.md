# Deploy WorkWell from the dev branch

This guide is for the exact integrated repository. Streamlit Community Cloud can deploy the Python application directly. GitHub's default branch can remain main; the deployment explicitly selects dev.

## Deployment status

The release is prepared and verified for dev. Creating the hosted application requires an authenticated Streamlit Community Cloud account and the GitHub connection consent flow. The current agent session has GitHub CLI access but no authenticated Streamlit browser session or Streamlit deployment tool. No hosted URL is claimed. The public Streamlit portal requires JavaScript and account interaction.

## Create the application

1. Open https://share.streamlit.io/ and sign in or create a Community Cloud account.
2. Connect the GitHub account icuutry and authorize access to the repository. Follow the platform's GitHub consent prompts.
3. Select Create app and the option for an existing GitHub application.
4. Set Repository to icuutry/WorkWellAgentCA6117, Branch to dev, and Main file path to app.py. Source files must be at the repository root; do not point to the ZIP archive.
5. Open Advanced settings and select Python 3.12. requirements.txt is installed automatically. validate.ps1 is a local Windows helper, not the cloud entry point.
6. For the first deployment, paste the following TOML into Secrets. This configuration requires no model credential and spends no API quota:

```toml
WORKWELL_OFFLINE = "1"
```

7. Save the settings and select Deploy. Wait for installation/startup logs and use the literal URL returned by Streamlit. A suggested custom name may be unavailable; use the generated URL if necessary.
8. Open the app as a visitor. Leave Team modules selected, choose a unique fictional user ID, generate a plan and check the visible offline-demo label.

## Enable the live provider later

Change Secrets in the hosted app settings only when real model requests are intended. The following is a placeholder template, not a usable credential:

```toml
WORKWELL_PROVIDER = "zhipu"
WORKWELL_MODEL = "glm-4-flash"
WORKWELL_OFFLINE = "0"
ZHIPU_API_KEY = "<YOUR_PRIVATE_KEY_ENTERED_ONLY_IN_STREAMLIT_SETTINGS>"
```

Replace the placeholder privately in Streamlit settings. Never paste a real key into GitHub, this document, a screenshot or public source. Streamlit loads root-level secrets into the application's environment. The prior temporary test credential is not included in this release and has not been configured for a public app.

Generate calls the selected provider only for a new valid check-in. Refreshing, viewing history and confirming an existing draft do not call it again. API calls still have the provider's quota/charges even though webpage hosting is free. To conserve quota, leave the shared demonstration in offline mode unless live operation is needed.

## Verify the shared demo

1. Use a new fictional ID and a simulated date. Start with completion Not applicable.
2. Enter a valid check-in, for example Neck, discomfort 3, fatigue 4, sitting 6 and no warning signs.
3. Generate and inspect explicit priorities, all three explanation fields, English sources and execution arrangements.
4. Accept or reject the draft and verify History/Audit log. Repeated buttons must not create duplicate records.
5. Advance the date by one day. If a prior accepted plan exists, report its completion. Change scores and generate the next plan.
6. Select Numbness in a separate check-in to verify a safety stop; no model call occurs for that input.

## Important hosting behavior

- Changes pushed to the selected dev branch update the deployed application. Keep a tested commit for the presentation and avoid changing dev during the live demo.
- Community Cloud apps without traffic for 12 hours can sleep. Open the app before presenting; a visitor with access can wake it.
- Local JSON files are not durable cloud storage. Restart/rebuild/hibernation may remove runtime history. For this simulated proof of concept, use new fictional IDs and recreate a short daily sequence. Reliable long-term history requires an external persistent store and separate validation.
- The app has no real-user authentication. Distinct fictional IDs separate demonstration histories but are not an access-control system.
- Share the actual returned application URL and a backup demo recording. Do not claim a deployment succeeded merely because the GitHub push succeeded.

## Troubleshooting

| Symptom | Check |
|---|---|
| Repository not listed | Correct GitHub account/owner, repository access and connection authorization |
| app.py not found | Branch dev and root entry point app.py; source was extracted rather than uploaded as a ZIP |
| Dependency installation fails | Python 3.12, requirements.txt and the actual cloud build log |
| No earlier accepted plan | First use requires Not applicable; rejected plans do not count as accepted history |
| This simulated day already has a record | Use the next date, or exact submitted input to recover a pending draft |
| Model error | Live mode/provider/model/key settings and provider quota; no automatic offline fallback occurs |
| Different visitors see shared history | Use distinct fictional IDs; the current app does not authenticate users |
| History disappeared after restart | Local cloud disk is temporary; replay the simulated scenario or add durable storage |

## Official references

- Deployment and branch selection: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- Secrets: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- App updates and sleep: https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
- Local storage limitations: https://docs.streamlit.io/develop/concepts/connections/connecting-to-data
