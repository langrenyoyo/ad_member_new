package com.example.idiomquiz.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Reference XML geometry, with the application's current palette and callbacks. */
@Composable
internal fun ReferenceToolbar(title: String, onBack: () -> Unit, height: Dp = 48.dp,
    titleSize: Int = 20, actions: @Composable RowScope.() -> Unit = {}) {
    Box(Modifier.fillMaxWidth().heightIn(min = height)) {
        Row(Modifier.fillMaxWidth().heightIn(min = height), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack, modifier = Modifier.size(48.dp)) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回")
            }
            Spacer(Modifier.weight(1f))
            actions()
        }
        Text(title, modifier = Modifier.align(Alignment.Center).padding(horizontal = 88.dp),
            fontSize = titleSize.sp, lineHeight = (titleSize + 8).sp, fontWeight = FontWeight.Bold,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center)
    }
}

@Composable
internal fun ReferencePanel(modifier: Modifier = Modifier, radius: Dp = 16.dp, padding: Dp = 16.dp,
    content: @Composable ColumnScope.() -> Unit) {
    Surface(modifier.fillMaxWidth(), shape = RoundedCornerShape(radius),
        color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, AppPalette.Border)) {
        Column(Modifier.padding(padding), verticalArrangement = Arrangement.spacedBy(8.dp), content = content)
    }
}

@Composable
internal fun ReferenceInput(value: String, onValueChange: (String) -> Unit, hint: String,
    modifier: Modifier = Modifier, prefix: String? = null,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
    trailing: (@Composable () -> Unit)? = null) {
    Surface(modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, AppPalette.Border)) {
        Row(Modifier.heightIn(min = 50.dp).padding(start = 14.dp, end = 10.dp),
            verticalAlignment = Alignment.CenterVertically) {
            prefix?.let {
                Text(it, Modifier.background(AppPalette.PrimarySoft, RoundedCornerShape(8.dp))
                    .padding(horizontal = 10.dp, vertical = 6.dp),
                    fontSize = 13.sp, fontWeight = FontWeight.Bold, color = AppPalette.Primary)
                Spacer(Modifier.width(10.dp))
            }
            BasicTextField(value, onValueChange, modifier = Modifier.weight(1f).padding(vertical = 12.dp)
                .semantics { contentDescription = hint }, singleLine = true,
                keyboardOptions = keyboardOptions, cursorBrush = SolidColor(AppPalette.Primary),
                textStyle = MaterialTheme.typography.bodyLarge.copy(color = AppPalette.Text),
                decorationBox = { field ->
                    Box { if (value.isEmpty()) Text(hint, style = MaterialTheme.typography.bodyLarge, color = AppPalette.Muted); field() }
                })
            trailing?.invoke()
        }
    }
}
