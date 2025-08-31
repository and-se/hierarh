<?xml version="1.0"?>
<!--
original source https://xmldiff.readthedocs.io/en/stable/advanced.html#making-a-visual-diff 
and
https://github.com/Shoobx/xmldiff/blob/master/docs/source/static/htmlformatter.xslt -->

<xsl:stylesheet version="1.0"
    xmlns:diff="http://namespaces.shoobx.com/diff"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <xsl:template name="mark-diff-insert">
        <ins class="diff-ins">
            <xsl:apply-templates/>
        </ins>
    </xsl:template>

    <xsl:template name="mark-diff-delete">
        <del class="diff-del">
            <xsl:apply-templates/>
        </del>
    </xsl:template>

    <xsl:template name="mark-diff-insert-formatting">
        <ins class="diff-ins-formatting">
            <xsl:apply-templates/>
        </ins>
    </xsl:template>

    <xsl:template name="mark-diff-delete-formatting">
        <del class="diff-del-formatting">
            <xsl:apply-templates/>
        </del>
    </xsl:template>

    <xsl:template match="diff:insert">
        <xsl:if test="normalize-space(text())!=''">
            <ins class="diff-ins-t">
                <xsl:apply-templates/>
            </ins>
        </xsl:if>
    </xsl:template>

    <xsl:template match="diff:delete">
        <xsl:if test="normalize-space(text())!=''"> 
            <del class="diff-del-t">    
                <xsl:apply-templates/>
            </del>
        </xsl:if>
    </xsl:template>

    <!-- If any major paragraph element is inside a diff tag, put the markup
        around the entire paragraph. -->
    <xsl:template match="p|h1|h2|h3|h4|h5|h6">
        <xsl:choose>
            <xsl:when test="ancestor-or-self::*[@diff:insert]">
                <xsl:copy>
                    <xsl:call-template name="mark-diff-insert" />
                </xsl:copy>
            </xsl:when>
            <xsl:when test="ancestor-or-self::*[@diff:delete]">
                <xsl:copy>
                    <xsl:call-template name="mark-diff-delete" />
                </xsl:copy>
            </xsl:when>
            <xsl:otherwise>
                <xsl:copy>
                    <xsl:apply-templates/>
                </xsl:copy>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <!-- Put diff markup in marked paragraph formatting tags. -->
    <xsl:template match="span[not(contains(@class, 'fnote'))]|b|i|u|strike|sub|sup">
        <xsl:choose>
            <xsl:when test="@diff:insert">
                <xsl:copy>
                    <xsl:call-template name="mark-diff-insert" />
                </xsl:copy>
            </xsl:when>
            <xsl:when test="@diff:delete">
                <xsl:copy>
                    <xsl:call-template name="mark-diff-delete" />
                </xsl:copy>
            </xsl:when>
            <xsl:when test="@diff:insert-formatting">
                <xsl:copy>
                    <xsl:call-template name="mark-diff-insert-formatting" />
                </xsl:copy>
            </xsl:when>
            <xsl:when test="@diff:delete-formatting">
                <xsl:copy>
                    <xsl:call-template name="mark-diff-delete-formatting" />
                </xsl:copy>
            </xsl:when>
            <xsl:otherwise>
                <xsl:copy>
                    <xsl:apply-templates/>
                </xsl:copy>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    
    <!-- FIXME Сноски разбираем отдельно, чтобы diff не ломал их структуру-->
    <xsl:template match="span[contains(@class, 'fnote')]">
        <xsl:choose>
            <xsl:when test="@diff:insert">
                <ins>
                    <xsl:copy>
                        <xsl:attribute name="class">fnote</xsl:attribute>   
                        <xsl:apply-templates />
                    </xsl:copy>
                </ins>
            </xsl:when>
            <xsl:when test="@diff:delete">
                <del>
                    <xsl:copy>
                        <xsl:attribute name="class">fnote</xsl:attribute>   
                        <xsl:apply-templates />
                    </xsl:copy>
                </del>
            </xsl:when>
            <xsl:otherwise>                
                <xsl:copy>                                   
                    <xsl:attribute name="class">fnote</xsl:attribute>   
                    <sup>[сноска]</sup>
                    <xsl:apply-templates select="*[local-name() != 'sup']"/>
                </xsl:copy>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    
    <!-- Удаление и добавление строки могут слиться в одну строку из 6 ячеек - разделяем -->
    <xsl:template match="tr[count(./td)>3]">
        <tr class="first3">
            <xsl:apply-templates select="td[position() &lt; 4]"/>
        </tr>
        <tr class="last3">
            <xsl:apply-templates select="td[position() >= 4]"/>
        </tr>
    </xsl:template>
    
    <!-- Put diff markup into pseudo-paragraph tags, if they act as paragraph. -->
    <xsl:template match="li|th|td|div">
        <xsl:variable name="localParas" select="para|h1|h2|h3|h4|h5|h6" />
        <xsl:copy>
            <!-- Иногда ячейка-заголовок задваивается как удаление и добавление. Следим, чтобы не выйти за 3 колонки, а то ломается таблица -->
            <xsl:if test="@colspan and not(following-sibling::*[@colspan] or preceding-sibling::*[@colspan])">
                <xsl:attribute name="colspan">
                    <xsl:value-of select="@colspan"/>
                </xsl:attribute>
            </xsl:if>
            
            <!-- вот так можно скопировать все атрибуты, чего xsl:copy не делает -->
            <!--<xsl:copy-of select="@*[not(namespace-uri() = 'http://namespaces.shoobx.com/diff')]"/>-->
            <xsl:choose>
                <xsl:when test="not($localParas) and ancestor-or-self::*[@diff:insert]">
                        <xsl:call-template name="mark-diff-insert" />                    
                </xsl:when>
                <xsl:when test="not($localParas) and ancestor-or-self::*[@diff:delete]">
                        <xsl:call-template name="mark-diff-delete" />                    
                </xsl:when>
                <xsl:otherwise>
                        <xsl:apply-templates/>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:copy>
    </xsl:template>

    <!-- =====[ Boilerplate ]=============================================== -->

    <!-- Remove all processing information -->
    <xsl:template match="//processing-instruction()" />

    <!-- Catch all with Identity Recursion -->
    <xsl:template match="@*|node()">
        <xsl:copy>
            <xsl:apply-templates select="@*|node()"/>
        </xsl:copy>
    </xsl:template>

    <!-- Main rule for whole document -->
    <xsl:template match="/">
        <xsl:apply-templates/>
    </xsl:template>

</xsl:stylesheet>
