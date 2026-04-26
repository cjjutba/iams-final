package com.iams.app.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavController
import androidx.navigation.compose.currentBackStackEntryAsState
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextTertiary

data class BottomNavTab(
    val label: String,
    val icon: ImageVector,
    val selectedIcon: ImageVector = icon,
    /**
     * Destination-route template used to match [NavController.currentDestination.route].
     * For destinations with optional query args (e.g. `student/history?scheduleId={scheduleId}`),
     * this must be the full template or the tab would never appear selected and the
     * enclosing Scaffold would hide the bottom bar.
     */
    val route: String,
    /**
     * Route actually passed to [NavController.navigate]. Defaults to [route] for plain
     * routes, but destinations with templated args need a concrete path here (e.g.
     * `student/history`) so the NavGraph resolves it with default/empty args.
     */
    val navRoute: String = route,
    val badgeCount: Int = 0,
)

@Composable
fun IAMSBottomBar(
    navController: NavController,
    tabs: List<BottomNavTab>,
) {
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = Background,
        shadowElevation = 4.dp,
        tonalElevation = 0.dp,
    ) {
        Column {
            // Subtle top divider
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(0.5.dp)
                    .background(Border.copy(alpha = 0.4f))
            )

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .windowInsetsPadding(WindowInsets.navigationBars)
                    .padding(horizontal = 16.dp)
                    .height(56.dp),
                horizontalArrangement = Arrangement.SpaceAround,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                tabs.forEach { tab ->
                    val selected = currentRoute == tab.route
                    val interactionSource = remember { MutableInteractionSource() }

                    val iconColor by animateColorAsState(
                        targetValue = if (selected) Primary else TextTertiary,
                        animationSpec = tween(200),
                        label = "iconColor",
                    )

                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .clickable(
                                interactionSource = interactionSource,
                                indication = null,
                                onClick = {
                                    if (currentRoute != tab.route) {
                                        navController.navigate(tab.navRoute) {
                                            popUpTo(tabs.first().navRoute) { saveState = true }
                                            launchSingleTop = true
                                            restoreState = true
                                        }
                                    }
                                },
                            ),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center,
                    ) {
                        if (tab.badgeCount > 0) {
                            BadgedBox(
                                badge = {
                                    Badge(
                                        containerColor = Color(0xFFDC2626),
                                        contentColor = Color.White,
                                    ) {
                                        Text(
                                            text = if (tab.badgeCount > 99) "99+" else tab.badgeCount.toString(),
                                            fontSize = 9.sp,
                                        )
                                    }
                                }
                            ) {
                                Icon(
                                    imageVector = if (selected) tab.selectedIcon else tab.icon,
                                    contentDescription = tab.label,
                                    modifier = Modifier.size(22.dp),
                                    tint = iconColor,
                                )
                            }
                        } else {
                            Icon(
                                imageVector = if (selected) tab.selectedIcon else tab.icon,
                                contentDescription = tab.label,
                                modifier = Modifier.size(22.dp),
                                tint = iconColor,
                            )
                        }
                        Text(
                            text = tab.label,
                            fontSize = 10.sp,
                            fontWeight = if (selected) FontWeight.Medium else FontWeight.Normal,
                            color = iconColor,
                            modifier = Modifier.padding(top = 2.dp),
                        )
                    }
                }
            }
        }
    }
}
