using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using UnityEditor;
using UnityEngine;

namespace GameAssetDb.Editor
{
    public class GameAssetDbWindow : EditorWindow
    {
        private const string ConfigFileName = "config.json";
        private Vector2 _scrollPosition;
        private string _searchQuery = string.Empty;
        private List<AssetSummary> _assets = new();
        private bool _isLoading;
        private string _statusMessage = string.Empty;

        [MenuItem("Window/Game Asset DB")]
        public static void ShowWindow()
        {
            var window = GetWindow<GameAssetDbWindow>("Game Asset DB");
            window.Show();
        }

        private void OnEnable()
        {
            _ = RefreshAssetsAsync();
        }

        private async Task RefreshAssetsAsync()
        {
            if (_isLoading)
            {
                return;
            }

            _isLoading = true;
            _statusMessage = "Loading assets...";
            Repaint();

            try
            {
                var config = await LoadConfigAsync();
                var client = new HttpClient
                {
                    BaseAddress = new Uri(config.ApiBaseUrl.TrimEnd('/') + "/")
                };

                var response = await client.GetAsync("assets?query=" + Uri.EscapeDataString(_searchQuery ?? string.Empty));
                response.EnsureSuccessStatusCode();
                var json = await response.Content.ReadAsStringAsync();
                var payload = JsonUtility.FromJson<AssetListResponse>(WrapJson(json));
                _assets = payload.items ?? new List<AssetSummary>();
                _statusMessage = $"Loaded {_assets.Count} assets.";
            }
            catch (Exception ex)
            {
                _statusMessage = "Failed to load assets: " + ex.Message;
                Debug.LogError(ex);
            }
            finally
            {
                _isLoading = false;
                Repaint();
            }
        }

        private void OnGUI()
        {
            using (new EditorGUILayout.HorizontalScope())
            {
                _searchQuery = EditorGUILayout.TextField("Search", _searchQuery);
                if (GUILayout.Button("Refresh", GUILayout.Width(80)))
                {
                    _ = RefreshAssetsAsync();
                }
            }

            EditorGUILayout.Space();

            if (_isLoading)
            {
                EditorGUILayout.LabelField("Loading...");
                return;
            }

            _scrollPosition = EditorGUILayout.BeginScrollView(_scrollPosition);
            foreach (var asset in _assets)
            {
                EditorGUILayout.BeginVertical("box");
                EditorGUILayout.LabelField(asset.name, EditorStyles.boldLabel);
                EditorGUILayout.LabelField("Version", asset.version);
                EditorGUILayout.BeginHorizontal();
                if (GUILayout.Button("Import"))
                {
                    Debug.Log($"Importing asset {asset.id}");
                    // TODO: Implement importer hook for project-specific pipelines.
                }
                if (GUILayout.Button("Open in Browser"))
                {
                    Application.OpenURL(asset.viewerUrl);
                }
                EditorGUILayout.EndHorizontal();
                EditorGUILayout.EndVertical();
            }
            EditorGUILayout.EndScrollView();

            EditorGUILayout.HelpBox(_statusMessage, MessageType.Info);
        }

        private static async Task<GameAssetDbConfig> LoadConfigAsync()
        {
            var configPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "GameAssetDB", ConfigFileName);
            if (!File.Exists(configPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(configPath));
                await File.WriteAllTextAsync(configPath, JsonUtility.ToJson(new GameAssetDbConfig(), true), Encoding.UTF8);
            }

            var json = await File.ReadAllTextAsync(configPath, Encoding.UTF8);
            var config = JsonUtility.FromJson<GameAssetDbConfig>(json);
            return config ?? new GameAssetDbConfig();
        }

        private static string WrapJson(string json)
        {
            if (json.TrimStart().StartsWith("{"))
            {
                return json;
            }

            return "{\"items\": " + json + "}";
        }

        [Serializable]
        private class GameAssetDbConfig
        {
            public string ApiBaseUrl = "https://game-asset-db.example.com/api";
        }

        [Serializable]
        private class AssetSummary
        {
            public string id;
            public string name;
            public string version;
            public string viewerUrl;
        }

        [Serializable]
        private class AssetListResponse
        {
            public List<AssetSummary> items;
        }
    }
}
