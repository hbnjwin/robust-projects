import type { NavigatorScreenParams } from "@react-navigation/native";
import type { StackScreenProps } from "@react-navigation/stack";
import type { BottomTabScreenProps } from "@react-navigation/bottom-tabs";
import type { CompositeScreenProps } from "@react-navigation/native";

// ---- 路由参数类型 ----
// 用泛型严格约束每个路由能接收的参数，从根源防止参数丢失

export type HomeStackParamList = {
  Home: undefined;
  Detail: { id: string; title: string }; // 必传参数，不允许 undefined
  Settings: undefined;
};

export type ProfileStackParamList = {
  Profile: undefined;
  EditProfile: { userId: string };
};

export type AuthStackParamList = {
  Login: undefined;
};

export type RootTabParamList = {
  HomeTab: NavigatorScreenParams<HomeStackParamList>;
  ProfileTab: NavigatorScreenParams<ProfileStackParamList>;
};

// ---- 屏幕 Props 类型 ----
// CompositeScreenProps 处理嵌套导航器的类型合并，确保深层页面既能访问
// 自己 Stack 的方法，也能访问外层 Tab 的方法

export type HomeScreenProps = CompositeScreenProps<
  StackScreenProps<HomeStackParamList, "Home">,
  BottomTabScreenProps<RootTabParamList>
>;

export type DetailScreenProps = CompositeScreenProps<
  StackScreenProps<HomeStackParamList, "Detail">,
  BottomTabScreenProps<RootTabParamList>
>;

export type SettingsScreenProps = CompositeScreenProps<
  StackScreenProps<HomeStackParamList, "Settings">,
  BottomTabScreenProps<RootTabParamList>
>;

export type ProfileScreenProps = CompositeScreenProps<
  StackScreenProps<ProfileStackParamList, "Profile">,
  BottomTabScreenProps<RootTabParamList>
>;

export type EditProfileScreenProps = CompositeScreenProps<
  StackScreenProps<ProfileStackParamList, "EditProfile">,
  BottomTabScreenProps<RootTabParamList>
>;

export type LoginScreenProps = StackScreenProps<AuthStackParamList, "Login">;
