import java.util.Properties
import java.security.MessageDigest
import com.android.build.api.instrumentation.AsmClassVisitorFactory
import com.android.build.api.instrumentation.ClassContext
import com.android.build.api.instrumentation.ClassData
import com.android.build.api.instrumentation.FramesComputationMode
import com.android.build.api.instrumentation.InstrumentationParameters
import com.android.build.api.instrumentation.InstrumentationScope
import org.objectweb.asm.ClassVisitor
import org.objectweb.asm.FieldVisitor
import org.objectweb.asm.MethodVisitor
import org.objectweb.asm.Opcodes

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}

/** Forward public material getters while leaving the vendor's ad/reward implementation intact.
 * This bridge is specific to adapter-taku-kuaishou 5.6.10.1.1.2 and fails on ABI changes.
 */
abstract class KuaishouContentBridgeFactory : AsmClassVisitorFactory<InstrumentationParameters.None> {
    override fun isInstrumentable(classData: ClassData) =
        classData.className == "com.anythink.network.ks.KSATRewardedVideoAdapter"

    override fun createClassVisitor(classContext: ClassContext, nextClassVisitor: ClassVisitor): ClassVisitor =
        object : ClassVisitor(Opcodes.ASM9, nextClassVisitor) {
            private var adFieldFound = false
            private var bridgeMethods = 0
            override fun visitField(access: Int, name: String, descriptor: String, signature: String?, value: Any?): FieldVisitor? {
                if (name == "g" && descriptor == "Lcom/kwad/sdk/api/KsRewardVideoAd;" && access and Opcodes.ACC_STATIC == 0) {
                    adFieldFound = true
                }
                return super.visitField(access, name, descriptor, signature, value)
            }
            override fun visitMethod(access: Int, name: String, descriptor: String, signature: String?, exceptions: Array<out String>?): MethodVisitor? {
                val visitor = super.visitMethod(access, name, descriptor, signature, exceptions)
                if (name != "getNetworkInfoMap" || descriptor != "()Ljava/util/Map;") return visitor
                check(access and (Opcodes.ACC_STATIC or Opcodes.ACC_ABSTRACT) == 0) { "Unsupported KS adapter method ABI" }
                bridgeMethods++
                return object : MethodVisitor(Opcodes.ASM9, visitor) {
                    override fun visitInsn(opcode: Int) {
                        if (opcode == Opcodes.ARETURN) {
                            super.visitVarInsn(Opcodes.ALOAD, 0)
                            super.visitFieldInsn(Opcodes.GETFIELD, "com/anythink/network/ks/KSATRewardedVideoAdapter", "g", "Lcom/kwad/sdk/api/KsRewardVideoAd;")
                            super.visitMethodInsn(Opcodes.INVOKESTATIC, "com/example/idiomquiz/ads/KuaishouRewardContent", "enrich", "(Ljava/util/Map;Lcom/kwad/sdk/api/KsRewardVideoAd;)Ljava/util/Map;", false)
                        }
                        super.visitInsn(opcode)
                    }
                }
            }
            override fun visitEnd() {
                check(adFieldFound && bridgeMethods == 1) { "KS adapter ABI changed; review the content bridge before upgrading" }
                super.visitEnd()
            }
        }
}

androidComponents {
    onVariants(selector().all()) { variant ->
        variant.instrumentation.transformClassesWith(KuaishouContentBridgeFactory::class.java, InstrumentationScope.ALL) {}
        variant.instrumentation.setAsmFramesComputationMode(FramesComputationMode.COMPUTE_FRAMES_FOR_INSTRUMENTED_METHODS)
    }
}

android {
    namespace = "com.example.idiomquiz"
    compileSdk = 35

    val anythinkAppId = providers.gradleProperty("anythinkAppId").getOrElse("")
    val anythinkAppKey = providers.gradleProperty("anythinkAppKey").getOrElse("")
    val anythinkSplashPlacement = providers.gradleProperty("anythinkSplashPlacement").getOrElse("")
    val localConfig = Properties().apply {
        val configFile = rootProject.file("local.properties")
        if (configFile.exists()) configFile.inputStream().use { load(it) }
    }
    val aliyunDeviceRiskAppKey = providers.gradleProperty("aliyunDeviceRiskAppKey")
        .getOrElse(localConfig.getProperty("aliyunDeviceRiskAppKey", ""))
    val riskAars = fileTree("libs") { include("Android-AliyunDevice-*.aar") }
    require(riskAars.files.size <= 1) { "Keep exactly one Aliyun device SDK version in app/libs" }
    require(aliyunDeviceRiskAppKey.all { it.isLetterOrDigit() || it in "-_." }) {
        "aliyunDeviceRiskAppKey contains invalid characters"
    }
    if (aliyunDeviceRiskAppKey.isNotBlank() || providers.gradleProperty("requireAliyunDeviceRisk").orNull == "true") {
        require(aliyunDeviceRiskAppKey.isNotBlank() && riskAars.files.size == 1) {
            "Aliyun device risk requires an AppKey and app/libs/Android-AliyunDevice-<version>.aar"
        }
    }
    val wechatConfig = Properties().apply {
        rootProject.file("wechat.properties").inputStream().use { load(it) }
    }
    val wechatAppId = providers.gradleProperty("wechatAppId")
        .getOrElse(wechatConfig.getProperty("appId"))
    val androidApplicationId = providers.gradleProperty("androidApplicationId")
        .getOrElse(wechatConfig.getProperty("applicationId"))

    // Release signing secrets live in root keystore.properties (gitignored).
    val keystorePropertiesFile = rootProject.file("keystore.properties")
    val keystoreProperties = Properties().apply {
        if (keystorePropertiesFile.exists()) {
            keystorePropertiesFile.inputStream().use { load(it) }
        }
    }
    val hasReleaseKeystore = keystorePropertiesFile.exists()

    defaultConfig {
        applicationId = androidApplicationId
        minSdk = 26
        targetSdk = 35
        versionCode = 8
        versionName = "1.0.7"
        val sourceDigest = MessageDigest.getInstance("SHA-256")
        (fileTree("src/main").files + file("build.gradle.kts")).sortedBy { it.relativeTo(projectDir).invariantSeparatorsPath }
            .forEach { sourceFile ->
                sourceDigest.update(sourceFile.relativeTo(projectDir).invariantSeparatorsPath.toByteArray(Charsets.UTF_8))
                sourceDigest.update(0.toByte())
                sourceDigest.update(sourceFile.readBytes())
            }
        val sourceFingerprint = sourceDigest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
        buildConfigField("String", "SOURCE_FINGERPRINT", "\"$sourceFingerprint\"")

        val apiBaseUrl = providers.gradleProperty("userApiBaseUrl")
            .getOrElse("https://hehe.hehkun.cn/api/app/v1/").trimEnd('/') + "/"
        require(apiBaseUrl.startsWith("https://")) { "userApiBaseUrl must use HTTPS" }
        require(!apiBaseUrl.contains('"') && !apiBaseUrl.contains('\\') && !apiBaseUrl.contains('\n'))
        val registrationGameId = providers.gradleProperty("registrationGameId").getOrElse(wechatConfig.getProperty("gameId")).toInt()
        require(registrationGameId > 0)
        buildConfigField("String", "USER_API_BASE_URL", "\"$apiBaseUrl\"")
        buildConfigField("int", "REGISTRATION_GAME_ID", registrationGameId.toString())

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

    signingConfigs {
        if (hasReleaseKeystore) {
            val storeFilePath = keystoreProperties.getProperty("storeFile")?.trim().orEmpty()
            val storePasswordValue = keystoreProperties.getProperty("storePassword").orEmpty()
            val keyAliasValue = keystoreProperties.getProperty("keyAlias")?.trim().orEmpty()
            val keyPasswordValue = keystoreProperties.getProperty("keyPassword").orEmpty()
            require(storeFilePath.isNotEmpty()) { "keystore.properties missing storeFile" }
            require(storePasswordValue.isNotEmpty()) { "keystore.properties missing storePassword" }
            require(keyAliasValue.isNotEmpty()) { "keystore.properties missing keyAlias" }
            require(keyPasswordValue.isNotEmpty()) { "keystore.properties missing keyPassword" }
            val releaseStoreFile = rootProject.file(storeFilePath)
            require(releaseStoreFile.isFile) {
                "Release keystore not found: ${releaseStoreFile.absolutePath}"
            }
            create("release") {
                storeFile = releaseStoreFile
                storePassword = storePasswordValue
                keyAlias = keyAliasValue
                keyPassword = keyPasswordValue
            }
        }
    }

    buildTypes {
        create("deviceTest") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".devtest"
            matchingFallbacks += "debug"
            buildConfigField("String", "USER_API_BASE_URL", "\"http://127.0.0.1:18080/api/app/v1/\"")
            buildConfigField("int", "REGISTRATION_GAME_ID", "1")
        }
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            if (hasReleaseKeystore) {
                signingConfig = signingConfigs.getByName("release")
            }
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
    implementation(files("libs/zxing-core-3.5.3.jar"))
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.3")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.3")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.3")

    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material")
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
    testImplementation("org.json:json:20240303")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
}
