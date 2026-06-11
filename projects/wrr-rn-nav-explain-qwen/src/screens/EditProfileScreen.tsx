import React, { useEffect } from "react";
import { View, Text, StyleSheet, Alert } from "react-native";
import type { EditProfileScreenProps } from "../navigation/types";

export default function EditProfileScreen({
  route,
  navigation,
}: EditProfileScreenProps) {
  const { userId } = route.params;

  // 与 DetailScreen 相同的参数校验逻辑
  useEffect(() => {
    if (!userId) {
      Alert.alert("参数错误", "缺少用户 ID，即将返回");
      navigation.goBack();
    }
  }, [userId, navigation]);

  // 编辑页离开保护：防止误触返回丢失编辑内容
  useEffect(() => {
    const unsubscribe = navigation.addListener("beforeRemove", (e) => {
      if (e.data.action.type === "GO_BACK") return;
      e.preventDefault();
      Alert.alert("确认离开？", "未保存的修改将丢失", [
        { text: "继续编辑", style: "cancel" },
        {
          text: "丢弃",
          style: "destructive",
          onPress: () => navigation.dispatch(e.data.action),
        },
      ]);
    });
    return unsubscribe;
  }, [navigation]);

  return (
    <View style={styles.container}>
      <Text style={styles.header}>编辑资料</Text>
      <Text style={styles.info}>用户 ID: {userId}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: "#fff" },
  header: { fontSize: 22, fontWeight: "bold", marginBottom: 16 },
  info: { fontSize: 16, color: "#444" },
});
