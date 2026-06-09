import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
} from "react-native";
import { useAuth } from "../context/AuthContext";

export default function LoginScreen() {
  const [name, setName] = useState("");
  const { login } = useAuth();

  const handleLogin = () => {
    const trimmed = name.trim();
    if (!trimmed) {
      Alert.alert("请输入用户名");
      return;
    }
    login(trimmed);
    // 登录后导航守卫会自动切换到 MainTab，无需手动导航
  };

  return (
    <View style={styles.container}>
      <Text style={styles.header}>登录</Text>
      <TextInput
        style={styles.input}
        placeholder="请输入用户名"
        value={name}
        onChangeText={setName}
        autoCapitalize="none"
      />
      <TouchableOpacity style={styles.button} onPress={handleLogin}>
        <Text style={styles.buttonText}>登录</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, backgroundColor: "#fff" },
  header: { fontSize: 28, fontWeight: "bold", textAlign: "center", marginBottom: 32 },
  input: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    marginBottom: 16,
  },
  button: {
    backgroundColor: "#3498db",
    padding: 14,
    borderRadius: 8,
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
