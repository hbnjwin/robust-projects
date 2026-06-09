import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useAuth } from "../context/AuthContext";
import type { SettingsScreenProps } from "../navigation/types";

export default function SettingsScreen({ navigation }: SettingsScreenProps) {
  const { user, logout } = useAuth();

  return (
    <View style={styles.container}>
      <Text style={styles.header}>设置</Text>
      {user && <Text style={styles.info}>当前用户: {user.name}</Text>}
      <TouchableOpacity
        style={styles.button}
        onPress={() => {
          logout();
          // 登出后导航守卫会自动切换到 AuthStack，无需手动 reset
        }}
      >
        <Text style={styles.buttonText}>退出登录</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: "#fff" },
  header: { fontSize: 24, fontWeight: "bold", marginBottom: 16 },
  info: { fontSize: 16, color: "#444", marginBottom: 24 },
  button: {
    backgroundColor: "#e74c3c",
    padding: 14,
    borderRadius: 8,
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
