import React, { useEffect } from "react";
import { View, Text, StyleSheet, Alert } from "react-native";
import type { DetailScreenProps } from "../navigation/types";

export default function DetailScreen({ route, navigation }: DetailScreenProps) {
  const { id, title } = route.params;

  // 关键修复 1：参数校验
  // 如果通过 deep link 或非法跳转进入，params 可能不完整，
  // 直接拦截并返回上一页，而不是渲染一个空页面
  useEffect(() => {
    if (!id || !title) {
      Alert.alert("参数错误", "缺少必要的页面参数，即将返回");
      navigation.goBack();
    }
  }, [id, title, navigation]);

  // 关键修复 2：防止意外返回丢失状态
  // beforeRemove 事件在页面即将被移出 Stack 时触发，
  // 可以在这里做确认弹窗、数据保存等操作
  useEffect(() => {
    const unsubscribe = navigation.addListener("beforeRemove", (e) => {
      // 如果是正常的 GO_BACK 操作，允许通过
      if (e.data.action.type === "GO_BACK") {
        return;
      }
      // 对于 RESET/NAVIGATE 等可能导致"跳到首页"的操作，
      // 先阻止，让用户确认
      e.preventDefault();
      Alert.alert("确认离开？", "当前页面数据可能丢失", [
        { text: "留下", style: "cancel" },
        {
          text: "离开",
          style: "destructive",
          onPress: () => navigation.dispatch(e.data.action),
        },
      ]);
    });
    return unsubscribe;
  }, [navigation]);

  return (
    <View style={styles.container}>
      <Text style={styles.label}>ID: {id}</Text>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.body}>
        这是详情页。返回时参数不会丢失，因为：{"\n\n"}
        1. 路由参数通过 TypeScript 泛型严格约束{"\n"}
        2. 使用 push 而非 navigate，每次进入都是独立路由实例{"\n"}
        3. beforeRemove 守卫阻止了非 GO_BACK 的意外导航
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: "#fff" },
  label: { fontSize: 14, color: "#666", marginBottom: 4 },
  title: { fontSize: 22, fontWeight: "bold", marginBottom: 16 },
  body: { fontSize: 14, lineHeight: 22, color: "#444" },
});
