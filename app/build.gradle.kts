plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}

android {
    namespace = "com.example.idiomquiz"
    compileSdk = 35

    val anythinkAppId = providers.gradleProperty("anythinkAppId").getOrElse("")
    val anythinkAppKey = providers.gradleProperty("anythinkAppKey").getOrElse("")
    val anythinkSplashPlacement = providers.gradleProperty("anythinkSplashPlacement").getOrElse("")
    val aliyunDeviceRiskAppKey = providers.gradleProperty("aliyunDeviceRiskAppKey").getOrElse("")
    val wechatAppId = providers.gradleProperty("wechatAppId")
        .getOrElse("wx91cfc0d66f031470")
    val androidApplicationId = providers.gradleProperty("androidApplicationId")
        .getOrElse("com.heshangzhilian.yazhiyiji")

    defaultConfig {
        applicationId = androidApplicationId
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        buildConfigField("String", "ANYTHINK_APP_ID", "\"$anythinkAppId\"")
        buildConfigField("String", "ANYTHINK_APP_KEY", "\"$anythinkAppKey\"")
        buildConfigField("String", "ANYTHINK_SPLASH_PLACEMENT", "\"$anythinkSplashPlacement\"")
        buildConfigField("String", "WECHAT_APP_ID", "\"$wechatAppId\"")
        buildConfigField("String", "ALIYUN_DEVICE_RISK_APP_KEY", "\"$aliyunDeviceRiskAppKey\"")

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }

    lint {
        // AnyThink's bundled download service triggers this check inside third-party bytecode.
        disable += "NotificationPermission"
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.3")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.3")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.3")

    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    // WeChat Open SDK, used for client-side authorization only.
    implementation("com.tencent.mm.opensdk:wechat-sdk-android-without-mta:6.8.0")

    // AnyThink (Necessary)
    implementation("com.anythink.sdk:core-taku:6.6.51")

    // Support (Necessary for the supplied adapters)
    implementation("com.android.support:appcompat-v7:28.0.0")

    // GDT
    implementation("com.anythink.sdk:adapter-taku-gdt:4.701.1571.1.2")
    implementation("com.qq.e.union:union:4.701.1571")

    // Baidu
    implementation("com.anythink.sdk:adapter-taku-baidu:9.460.1.2")
    implementation("mobi.baidu.sdk:mobads:9.460")

    // Kuaishou
    implementation("com.anythink.sdk:adapter-taku-kuaishou:5.6.10.1.1.2")
    implementation("com.anythink.sdk:sdk-ads-kuaishou:5.6.10.1")
    implementation("com.android.support:design:28.0.0")

    // Csj / Pangle
    implementation("com.anythink.sdk:adapter-taku-csj:7.6.1.2.1.3")
    implementation("com.pangle.cn:ads-sdk-pro:7.6.1.2")

    // AnyThink Kuying (Adx)
    implementation("com.anythink.sdk:adapter-taku-sdm:6.5.80.1.0")
    implementation("com.smartdigimkttech.sdk:sdm-sdk-cn:6.5.80")

    // Aliyun device risk SDK is distributed as an AAR from the Aliyun console.
    // Put Android-AliyunDevice-<version>.aar in app/libs when the backend AppKey is available.
    val aliyunDeviceRiskAars = fileTree("libs") {
        include("Android-AliyunDevice-*.aar")
    }
    if (!aliyunDeviceRiskAars.isEmpty) {
        implementation(files(aliyunDeviceRiskAars))
    }

    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
}
