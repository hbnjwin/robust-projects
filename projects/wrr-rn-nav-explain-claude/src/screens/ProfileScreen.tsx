import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useAuth } from "../context/AuthContext";
import type { ProfileScreenProps } from "../navigation/types";

export default function ProfileScreen({ navigation }: ProfileScreenProps) {
  const { user } = useAuth();

  return (
    <View style={styles.container}>
      <Text style={styles.header}>个人资料</Text>
      {user && (
        <>
          <Text style={styles.info}>用户名: {user.name}</Text>
          <Text style={styles.info}>用户 ID: {user.id}</Text>
          <TouchableOpacity
            style={styles.button}
            onPress={() =>
              navigation.push("EditProfile", { userId: user.id })
            }
          >
            <Text style={styles.buttonText}>编辑资料</Text>
          </TouchableOpacity>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: "#fff" },
  header: { fontSize: 24, fontWeight: "bold", marginBottom: 16 },
  info: { fontSize: 16, color: "#444", marginBottom: 8 },
  button: {
    marginTop: 16,
    backgroundColor: "#3498db",
    padding: 14,
    borderRadius: 8,
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
