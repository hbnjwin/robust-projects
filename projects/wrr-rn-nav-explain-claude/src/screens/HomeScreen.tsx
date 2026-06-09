import React from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from "react-native";
import type { HomeScreenProps } from "../navigation/types";

const ITEMS = [
  { id: "1", title: "React Navigation 基础" },
  { id: "2", title: "嵌套导航器" },
  { id: "3", title: "参数传递" },
  { id: "4", title: "导航守卫" },
];

export default function HomeScreen({ navigation }: HomeScreenProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.header}>首页</Text>
      <FlatList
        data={ITEMS}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.item}
            onPress={() => {
              // 关键修复：用 push 而不是 navigate
              // navigate 会复用已有的同名路由（导致参数被旧值覆盖），
              // push 总是创建新路由实例，参数独立不互相干扰
              navigation.push("Detail", { id: item.id, title: item.title });
            }}
          >
            <Text style={styles.itemText}>{item.title}</Text>
            <Text style={styles.arrow}>→</Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  header: { fontSize: 24, fontWeight: "bold", padding: 16 },
  item: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#ccc",
  },
  itemText: { fontSize: 16 },
  arrow: { fontSize: 18, color: "#999" },
});
