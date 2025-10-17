macroScript GameAssetDbInstaller
category:"Game Asset DB"
toolTip:"Install Game Asset DB"
(
    on execute do
    (
        python.executeFile @"$(getDir #userScripts)\\game_asset_db_plugin.py"
        messageBox "Game Asset DB plugin scripts loaded. Add toolbar buttons via Customize UI." title:"Game Asset DB"
    )
)
