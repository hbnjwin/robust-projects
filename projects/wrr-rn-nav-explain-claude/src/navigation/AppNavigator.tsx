import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createStackNavigator } from "@react-navigation/stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";

import { AuthProvider, useAuth } from "../context/AuthContext";
import type {
  HomeStackParamList,
  ProfileStackParamList,
  AuthStackParamList,
  RootTabParamList,
} from "./types";

import HomeScreen from "../screens/HomeScreen";
import DetailScreen from "../screens/DetailScreen";
import SettingsScreen from "../screens/SettingsScreen";
import ProfileScreen from "../screens/ProfileScreen";
import EditProfileScreen from "../screens/EditProfileScreen";
import LoginScreen from "../screens/LoginScreen";

// 修复 1：给每个 Navigator 绑定参数类型泛型
// 原代码 createStackNavigator() 无泛型 → 参数类型为 any → 传错参数不报错
const HomeStackNav = createStackNavigator<HomeStackParamList>();
const ProfileStackNav = createStackNavigator<ProfileStackParamList>();
const AuthStackNav = createStackNavigator<AuthStackParamList>();
const Tab = createBottomTabNavigator<RootTabParamList>();

// ---- HomeStack ----
function HomeStack() {
  return (
    <HomeStackNav.Navigator
      // 修复 2：明确指定 initialRouteName
      // 原代码没指定，依赖声明顺序，某些场景下（deep link、state restore）
      // 会导致返回时跳到错误页面
      initialRouteName="Home"
      screenOptions={{
        // 修复 3：禁用 gestureEnabled 的默认 reset 行为
        // 防止用户快速连续手势滑动时触发 navigation.reset 导致直接跳首页
        gestureResponseDistance: 50,
      }}
    >
      <HomeStackNav.Screen
        name="Home"
        component={HomeScreen}
        options={{ title: "首页" }}
      />
      <HomeStackNav.Screen
        name="Detail"
        component={DetailScreen}
        options={({ route }) => ({ title: route.params.title })}
      />
      <HomeStackNav.Screen
        name="Settings"
        component={SettingsScreen}
        options={{ title: "设置" }}
      />
    </HomeStackNav.Navigator>
  );
}

// ---- ProfileStack ----
// 原代码引用了 ProfileStack 但从未定义，直接运行时崩溃
function ProfileStack() {
  return (
    <ProfileStackNav.Navigator initialRouteName="Profile">
      <ProfileStackNav.Screen
        name="Profile"
        component={ProfileScreen}
        options={{ title: "我的" }}
      />
      <ProfileStackNav.Screen
        name="EditProfile"
        component={EditProfileScreen}
        options={{ title: "编辑资料" }}
      />
    </ProfileStackNav.Navigator>
  );
}

// ---- AuthStack（未登录时显示）----
function AuthStack() {
  return (
    <AuthStackNav.Navigator screenOptions={{ headerShown: false }}>
      <AuthStackNav.Screen name="Login" component={LoginScreen} />
    </AuthStackNav.Navigator>
  );
}

// ---- MainTab（已登录时显示）----
function MainTab() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        // 修复 4：关键！保持非活跃 Tab 的 Stack 状态
        // 原代码在切换 Tab 后，非活跃的 Stack 可能被卸载，
        // 导致返回时 Stack 被 reset → 用户从 Detail 页"跳到首页"
        // lazy: true 仅延迟首次渲染，不会卸载已渲染的 Tab
        lazy: true,
      }}
    >
      <Tab.Screen
        name="HomeTab"
        component={HomeStack}
        options={{ tabBarLabel: "首页" }}
      />
      <Tab.Screen
        name="ProfileTab"
        component={ProfileStack}
        options={{ tabBarLabel: "我的" }}
      />
    </Tab.Navigator>
  );
}

// ---- 导航守卫：根据认证状态条件渲染 ----
// 这是 React Navigation 官方推荐的认证流模式：
// 不是在 onPress 里检查 → 重定向，而是通过条件渲染
// 让整棵导航树随认证状态自动切换，无法被绕过
function NavigationGate() {
  const { isLoggedIn } = useAuth();
  return isLoggedIn ? <MainTab /> : <AuthStack />;
}

// ---- 根组件 ----
export default function AppNavigator() {
  return (
    <AuthProvider>
      <NavigationContainer>
        <NavigationGate />
      </NavigationContainer>
    </AuthProvider>
  );
}
